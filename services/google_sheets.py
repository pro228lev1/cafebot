import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import logging
import os
import time
import json
from config.settings import Config

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    def __init__(self):
        self.is_local_mode = Config.LOCAL_MODE
        self.spreadsheet = None
        self.client = None
        self.timezone = pytz.timezone(Config.TIMEZONE)
        self.cache = {
            'menu': {'data': None, 'timestamp': None},
            'employees': {'data': None, 'timestamp': None},
            'orders': {'data': None, 'timestamp': None},
            'settings': {'data': None, 'timestamp': None}
        }
        self.CACHE_TTL = 300  # 5 минут кэширования

        if not self.is_local_mode:
            self._init_google_client()

    def _init_google_client(self):
        """Инициализация подключения к Google Sheets с детальной диагностикой и обработкой ошибок аутентификации"""
        try:
            logger.info("🔍 Попытка подключения к Google Sheets...")
            logger.info(f"📄 Путь к credentials: {Config.GOOGLE_CREDENTIALS_PATH}")
            logger.info(f"🆔 SPREADSHEET_ID: {Config.SPREADSHEET_ID}")

            # Проверка существования файла credentials
            if not os.path.exists(Config.GOOGLE_CREDENTIALS_PATH):
                logger.error(f"❌ Файл credentials не найден: {Config.GOOGLE_CREDENTIALS_PATH}")
                logger.error("💡 Совет: Убедитесь, что файл google_auth.json существует и находится в правильной папке")
                logger.error("💡 Путь к файлу должен быть: " + os.path.abspath(Config.GOOGLE_CREDENTIALS_PATH))
                raise FileNotFoundError(f"Credentials file not found at {Config.GOOGLE_CREDENTIALS_PATH}")

            # Проверка содержимого файла credentials
            try:
                with open(Config.GOOGLE_CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        logger.error("❌ Файл credentials пустой!")
                        raise ValueError("Credentials file is empty")
                    # Проверяем, что это JSON
                    json.loads(content)
                    logger.info("✅ Файл credentials содержит корректный JSON")
            except json.JSONDecodeError:
                logger.error("❌ Файл credentials не является корректным JSON!")
                logger.error("💡 Совет: Скачайте новый файл JSON из Google Cloud Console")
                raise
            except Exception as e:
                logger.error(f"❌ Ошибка чтения файла credentials: {str(e)}")
                raise

            # Попытка аутентификации
            logger.info("🔑 Попытка аутентификации в Google API...")
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        logger.info(f"🔄 Попытка подключения #{attempt + 1} из {max_attempts}")
                        time.sleep(2)

                    scope = [
                        "https://spreadsheets.google.com/feeds",
                        "https://www.googleapis.com/auth/drive",
                        "https://www.googleapis.com/auth/spreadsheets"
                    ]

                    creds = Credentials.from_service_account_file(
                        Config.GOOGLE_CREDENTIALS_PATH,
                        scopes=scope
                    )

                    self.client = gspread.authorize(creds)
                    logger.info("✅ Успешная аутентификация в Google API")
                    break

                except Exception as auth_error:
                    logger.error(f"❌ Ошибка аутентификации (попытка {attempt + 1}/{max_attempts}): {str(auth_error)}")
                    if attempt == max_attempts - 1:
                        logger.error("❌ Все попытки аутентификации неудачны")
                        logger.error("💡 ВОЗМОЖНЫЕ ПРИЧИНЫ И РЕШЕНИЯ:")
                        logger.error("1. Неверный файл сервисного аккаунта")
                        logger.error("   - Удалите текущий файл google_auth.json")
                        logger.error("   - Скачайте НОВЫЙ файл JSON из Google Cloud Console")
                        logger.error("   - Сохраните его как config/google_auth.json")

                        logger.error("2. Проблема с системным временем")
                        logger.error("   - Убедитесь, что на вашем компьютере правильное время и дата")
                        logger.error("   - Разница во времени не должна превышать 5 минут")

                        logger.error("3. Сервисный аккаунт отключен")
                        logger.error("   - Перейдите в Google Cloud Console → IAM & Admin")
                        logger.error("   - Убедитесь, что сервисный аккаунт активен")

                        logger.error("4. Нет доступа к таблице")
                        logger.error("   - Откройте Google Таблицу → нажмите 'Поделиться'")
                        logger.error("   - Добавьте email из файла google_auth.json с правами 'Редактор'")

                        logger.error("\n💡 ВРЕМЕННОЕ РЕШЕНИЕ:")
                        logger.error("Чтобы продолжить работу, установите в .env:")
                        logger.error("LOCAL_MODE=True")

                        raise auth_error

            # Открытие таблицы
            logger.info(f"📄 Попытка открыть таблицу с ID: {Config.SPREADSHEET_ID}")
            self.spreadsheet = self.client.open_by_key(Config.SPREADSHEET_ID)
            logger.info(f"✅ Таблица успешно открыта: {self.spreadsheet.title}")

            # Проверка наличия всех необходимых листов
            required_sheets = ["Сотрудники", "Меню", "Заказы", "Настройки"]
            existing_sheets = [sheet.title for sheet in self.spreadsheet.worksheets()]

            logger.info(f"📋 Доступные листы: {', '.join(existing_sheets)}")

            for sheet in required_sheets:
                if sheet not in existing_sheets:
                    logger.warning(f"⚠️ Отсутствует обязательный лист: {sheet}")
                    self._create_required_sheet(sheet)
                else:
                    logger.info(f"✅ Лист '{sheet}' существует")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка подключения к Google Sheets: {str(e)}", exc_info=True)

            logger.warning("\n💡 РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ:")
            logger.warning("1. Проверьте правильность SPREADSHEET_ID в .env")
            logger.warning("2. Проверьте наличие и содержимое файла config/google_auth.json")
            logger.warning("3. Убедитесь, что системное время на компьютере правильное")
            logger.warning("4. Временно установите LOCAL_MODE=True в .env для тестирования")

            self.spreadsheet = None

    def _create_required_sheet(self, sheet_name):
        """Создание обязательного листа с правильной структурой (БЕЗ категории в меню)"""
        try:
            logger.info(f"🔧 Создаю отсутствующий лист '{sheet_name}'...")

            if sheet_name == "Сотрудники":
                new_sheet = self.spreadsheet.add_worksheet(title="Сотрудники", rows=100, cols=5)
                new_sheet.append_row(["Telegram ID", "ФИО", "Роль", "Статус", "Дата регистрации"])
                logger.info("✅ Лист 'Сотрудники' успешно создан с правильной структурой")

            elif sheet_name == "Меню":
                new_sheet = self.spreadsheet.add_worksheet(title="Меню", rows=100, cols=8)
                new_sheet.append_row([
                    "ID", "Кафе", "Название", "Описание",
                    "Активно", "Дата_начала", "Дата_окончания", "Цена"
                ])

                today = datetime.now(self.timezone).strftime("%Y-%m-%d")
                next_year = (datetime.now(self.timezone) + timedelta(days=365)).strftime("%Y-%m-%d")

                test_dishes = [
                    [1, "Coffee Time", "Борщ", "Свекольный суп с говядиной", "Да", today, next_year, 250],
                    [2, "Coffee Time", "Котлета", "Куриная котлета с гречкой", "Да", today, next_year, 300],
                    [3, "Coffee Time", "Салат Цезарь", "Салат с курицей и соусом", "Да", today, next_year, 200],
                    [4, "Coffee Time", "Чай черный", "Черный чай с лимоном", "Да", today, next_year, 50],
                    [5, "Coffee Time", "Компот", "Фруктовый компот", "Да", today, next_year, 70],
                    [6, "Coffee Time", "Хлеб", "Свежий белый хлеб", "Да", today, next_year, 30]
                ]

                for dish in test_dishes:
                    new_sheet.append_row(dish)

                logger.info("✅ Лист 'Меню' успешно создан с тестовыми данными (БЕЗ категории)")

            elif sheet_name == "Заказы":
                new_sheet = self.spreadsheet.add_worksheet(title="Заказы", rows=100, cols=8)
                new_sheet.append_row([
                    "ID", "Дата_заказа", "Дата_доставки", "Сотрудник",
                    "Кафе", "Состав", "Сумма", "Статус"
                ])
                logger.info("✅ Лист 'Заказы' успешно создан")

            elif sheet_name == "Настройки":
                new_sheet = self.spreadsheet.add_worksheet(title="Настройки", rows=100, cols=3)
                new_sheet.append_row(["Ключ", "Значение", "Описание"])

                default_settings = [
                    ["order_deadline_hour", "10", "Час дедлайна заказа"],
                    ["order_deadline_minute", "0", "Минуты дедлайна заказа"],
                    ["allowed_order_days", "1", "Дней вперед для заказа"],
                    ["default_cafe", "Coffee Time", "Кафе по умолчанию"],
                    ["default_delivery_time", "13:00-14:00", "Время доставки по умолчанию"]
                ]

                for setting in default_settings:
                    new_sheet.append_row(setting)

                logger.info("✅ Лист 'Настройки' успешно создан с настройками по умолчанию")

        except Exception as e:
            logger.error(f"❌ Не удалось создать лист '{sheet_name}': {str(e)}", exc_info=True)

    def get_worksheet(self, name):
        """Получение листа таблицы с автоматическим созданием при отсутствии"""
        if self.is_local_mode:
            logger.warning("⚠️ Работаю в ЛОКАЛЬНОМ режиме (без Google Sheets)")
            return None

        if not self.spreadsheet:
            logger.error("❌ Нет подключения к Google Sheets")
            return None

        try:
            worksheet = self.spreadsheet.worksheet(name)
            logger.debug(f"✅ Лист '{name}' успешно получен")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"❌ Лист '{name}' не найден в таблице")
            self._create_required_sheet(name)
            try:
                return self.spreadsheet.worksheet(name)
            except Exception as e:
                logger.error(f"❌ Окончательная ошибка получения листа '{name}': {str(e)}")
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения листа '{name}': {str(e)}", exc_info=True)
            return None

    def _get_cached_data(self, cache_key, fetch_func):
        """Получение данных с кэшированием"""
        if self.is_local_mode:
            return fetch_func()

        current_time = datetime.now().timestamp()
        cached = self.cache[cache_key]

        if cached['data'] is not None and (current_time - cached['timestamp']) < self.CACHE_TTL:
            return cached['data']

        try:
            data = fetch_func()
            self.cache[cache_key] = {'data': data, 'timestamp': current_time}
            return data
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных для {cache_key}: {str(e)}")
            return cached['data'] if cached['data'] is not None else []

    def get_employees(self):
        def fetch_employees():
            if self.is_local_mode:
                return [
                    {"Telegram ID": "5960210066", "ФИО": "Тестовый Пользователь", "Роль": "employee",
                     "Статус": "active", "Дата регистрации": "2024-12-07"},
                    {"Telegram ID": str(Config.ADMIN_TELEGRAM_ID), "ФИО": "Администратор", "Роль": "manager",
                     "Статус": "active", "Дата регистрации": "2024-12-07"}
                ]

            worksheet = self.get_worksheet("Сотрудники")
            if not worksheet:
                return []

            try:
                all_values = worksheet.get_all_values()
                if not all_values:
                    return []

                headers = all_values[0]
                required_headers = ["Telegram ID", "ФИО", "Роль", "Статус", "Дата регистрации"]
                missing_headers = [h for h in required_headers if h not in headers]
                if missing_headers:
                    logger.error(f"❌ Отсутствуют заголовки: {', '.join(missing_headers)}")
                    return []

                records = []
                for row in all_values[1:]:
                    if len(row) >= len(required_headers):
                        record = {}
                        for i, header in enumerate(required_headers):
                            record[header] = row[i] if i < len(row) else ""
                        records.append(record)

                return records

            except Exception as e:
                logger.error(f"❌ Ошибка получения сотрудников: {str(e)}", exc_info=True)
                return []

        return self._get_cached_data('employees', fetch_employees)

    def get_active_dishes(self):
        def fetch_dishes():
            if self.is_local_mode:
                return [
                    {"ID": "1", "Название": "Борщ", "Описание": "Свекольный суп с говядиной", "Активно": "Да",
                     "Цена": 250, "Кафе": "Coffee Time"},
                    {"ID": "2", "Название": "Котлета", "Описание": "Куриная котлета с гречкой", "Активно": "Да",
                     "Цена": 300, "Кафе": "Coffee Time"},
                    {"ID": "3", "Название": "Салат Цезарь", "Описание": "Салат с курицей и соусом", "Активно": "Да",
                     "Цена": 200, "Кафе": "Coffee Time"},
                    {"ID": "4", "Название": "Чай черный", "Описание": "Черный чай с лимоном", "Активно": "Да",
                     "Цена": 50, "Кафе": "Coffee Time"}
                ]

            worksheet = self.get_worksheet("Меню")
            if not worksheet:
                return []

            try:
                records = worksheet.get_all_records()
                now = datetime.now(self.timezone).strftime("%Y-%m-%d")
                active_dishes = []

                for dish in records:
                    is_active = str(dish.get("Активно", "")).strip().lower() in ["да", "1", "true", "yes"]

                    start_date = str(dish.get("Дата_начала", "")).strip()
                    end_date = str(dish.get("Дата_окончания", "")).strip()

                    start_check = not start_date or start_date[:10] <= now
                    end_check = not end_date or end_date[:10] >= now

                    if is_active and start_check and end_check:
                        dish["ID"] = str(dish.get("ID", ""))
                        dish["Название"] = dish.get("Название", "Без названия")
                        dish["Описание"] = dish.get("Описание", "")
                        dish["Кафе"] = dish.get("Кафе", "Coffee Time")

                        price_raw = dish.get("Цена", "0")
                        price_str = str(price_raw).replace(" ", "").replace("₽", "").replace(",", ".")
                        try:
                            dish["Цена"] = int(float(price_str))
                        except (ValueError, TypeError):
                            dish["Цена"] = 0
                            logger.warning(f"⚠️ Неверный формат цены: '{price_raw}' для '{dish['Название']}'")

                        active_dishes.append(dish)

                return active_dishes

            except Exception as e:
                logger.error(f"❌ Ошибка получения меню: {str(e)}", exc_info=True)
                return []

        return self._get_cached_data('menu', fetch_dishes)

    # ✅ ДОБАВЛЕННЫЙ МЕТОД — ОБЯЗАТЕЛЕН ДЛЯ АДМИН-ПАНЕЛИ
    def toggle_dish_status(self, dish_id: int) -> bool:
        """
        Переключает статус блюда (Да ↔ Нет) по ID в листе 'Меню'.
        Возвращает True при успехе, False — если не найдено или ошибка.
        """
        if self.is_local_mode:
            logger.info(f"[ЛОКАЛЬНЫЙ РЕЖИМ] Переключение статуса блюда ID {dish_id}")
            return True

        try:
            worksheet = self.get_worksheet("Меню")
            if not worksheet:
                logger.error("❌ Не удалось получить лист 'Меню'")
                return False

            all_values = worksheet.get_all_values()
            if not all_values:
                logger.warning("⚠️ Лист 'Меню' пуст")
                return False

            headers = [h.strip().lower() for h in all_values[0]]
            try:
                id_col = headers.index("id")
                active_col = headers.index("активно")
            except ValueError as e:
                logger.error(f"❌ Колонки ID/Активно не найдены. Заголовки: {headers}")
                return False

            # Поиск по ID (начиная со строки 2)
            for row_idx in range(1, len(all_values)):  # row_idx = 1 → 2-я строка в таблице
                row = all_values[row_idx]
                if len(row) <= id_col:
                    continue
                try:
                    row_id = str(row[id_col]).strip()
                    if row_id == str(dish_id):
                        current = str(row[active_col]).strip().lower() if active_col < len(row) else ""
                        new_status = "Нет" if current in ("да", "yes", "1", "true", "+", "✓") else "Да"

                        # Обновление ячейки (нумерация с 1)
                        worksheet.update_cell(row_idx + 1, active_col + 1, new_status)

                        # Сброс кэша
                        self.cache['menu'] = {'data': None, 'timestamp': None}
                        logger.info(f"✅ Статус блюда ID {dish_id} переключён на '{new_status}'")
                        return True
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки строки {row_idx + 1}: {e}")
                    continue

            logger.warning(f"⚠️ Блюдо ID {dish_id} не найдено")
            return False

        except Exception as e:
            logger.error(f"❌ Ошибка toggle_dish_status для ID {dish_id}: {e}", exc_info=True)
            return False

    def add_dish(self, dish_name, description, price, cafe="Coffee Time"):
        if self.is_local_mode:
            logger.info(f"🍽️ [ЛОКАЛЬНЫЙ РЕЖИМ] Добавление блюда: {dish_name}, {price}₽")
            return True

        try:
            worksheet = self.get_worksheet("Меню")
            if not worksheet:
                return False

            all_values = worksheet.get_all_values()
            next_id = len(all_values)  # т.к. заголовок = 1 строка

            today = datetime.now(self.timezone).strftime("%Y-%m-%d")
            next_year = (datetime.now(self.timezone) + timedelta(days=365)).strftime("%Y-%m-%d")

            worksheet.append_row([
                str(next_id),
                cafe,
                dish_name,
                description,
                "Да",
                today,
                next_year,
                str(price)
            ])

            self.cache['menu'] = {'data': None, 'timestamp': None}
            logger.info(f"✅ Блюдо добавлено: {dish_name}, ID: {next_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка добавления блюда: {str(e)}", exc_info=True)
            return False

    def delete_dish(self, dish_id):
        if self.is_local_mode:
            logger.info(f"🗑️ [ЛОКАЛЬНЫЙ РЕЖИМ] Удаление блюда ID: {dish_id}")
            return True

        try:
            worksheet = self.get_worksheet("Меню")
            if not worksheet:
                return False

            cell = worksheet.find(str(dish_id))
            if not cell:
                logger.warning(f"❌ Блюдо ID {dish_id} не найдено")
                return False

            worksheet.delete_rows(cell.row)
            self.cache['menu'] = {'data': None, 'timestamp': None}
            logger.info(f"✅ Блюдо ID {dish_id} удалено")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка удаления блюда: {str(e)}", exc_info=True)
            return False

    def get_all_orders(self):
        def fetch_orders():
            if self.is_local_mode:
                return [
                    {"ID": "101", "Дата_заказа": "2024-12-07", "Состав": "Борщ x1, Котлета x1", "Сумма": "550",
                     "Статус": "active"},
                    {"ID": "98", "Дата_заказа": "2024-12-06", "Состав": "Салат Цезарь x1", "Сумма": "200",
                     "Статус": "delivered"}
                ]

            worksheet = self.get_worksheet("Заказы")
            if not worksheet:
                return []

            try:
                records = worksheet.get_all_records()
                return records
            except Exception as e:
                logger.error(f"❌ Ошибка получения заказов: {str(e)}", exc_info=True)
                return []

        return self._get_cached_data('orders', fetch_orders)

    def get_active_orders(self):
        all_orders = self.get_all_orders()
        return [order for order in all_orders if order.get("Статус", "").lower() in ["active", "pending"]]

    def get_orders_report(self, period):
        all_orders = self.get_all_orders()

        if self.is_local_mode:
            return {
                'total_amount': 750,
                'total_orders': 2,
                'unique_customers': 1,
                'popular_dishes': [
                    {"name": "Борщ", "count": 1},
                    {"name": "Котлета", "count": 1},
                    {"name": "Салат Цезарь", "count": 1}
                ]
            }

        try:
            now = datetime.now(self.timezone)
            filtered_orders = []

            for order in all_orders:
                order_date = order.get("Дата_заказа", "")
                try:
                    order_datetime = datetime.strptime(order_date, "%Y-%m-%d")
                    order_datetime = self.timezone.localize(order_datetime)

                    if period == "сегодня":
                        if order_datetime.date() == now.date():
                            filtered_orders.append(order)
                    elif period == "неделя":
                        week_ago = now - timedelta(days=7)
                        if order_datetime >= week_ago:
                            filtered_orders.append(order)
                    elif period == "месяц":
                        month_ago = now - timedelta(days=30)
                        if order_datetime >= month_ago:
                            filtered_orders.append(order)
                    else:
                        filtered_orders.append(order)
                except (ValueError, TypeError):
                    continue

            total_amount = sum(int(order.get("Сумма", 0)) for order in filtered_orders)
            total_orders = len(filtered_orders)
            unique_customers = len(set(order.get("Сотрудник", "") for order in filtered_orders))

            dish_counts = {}
            for order in filtered_orders:
                items = order.get("Состав", "").split("; ")
                for item in items:
                    if "x" in item:
                        try:
                            dish_name = item.split("x")[0].strip()
                            dish_counts[dish_name] = dish_counts.get(dish_name, 0) + 1
                        except:
                            continue

            popular_dishes = sorted(dish_counts.items(), key=lambda x: x[1], reverse=True)
            popular_dishes = [{"name": name, "count": count} for name, count in popular_dishes[:10]]

            return {
                'total_amount': total_amount,
                'total_orders': total_orders,
                'unique_customers': unique_customers,
                'popular_dishes': popular_dishes
            }

        except Exception as e:
            logger.error(f"❌ Ошибка генерации отчета: {str(e)}", exc_info=True)
            return {}

    def add_order(self, user_id, cart_items):
        if self.is_local_mode:
            logger.info(f"📦 [ЛОКАЛЬНЫЙ РЕЖИМ] Заказ от {user_id}: {cart_items}")
            return True

        try:
            worksheet = self.get_worksheet("Заказы")
            if not worksheet:
                return False

            all_values = worksheet.get_all_values()
            next_id = len(all_values)

            items_text = "; ".join([
                f"{item['Название']} x{item['quantity']}" for item in cart_items
            ])

            total_price = sum(item.get('Цена', 0) * item['quantity'] for item in cart_items)
            now = datetime.now(self.timezone)
            delivery_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            order_date = now.strftime("%Y-%m-%d")

            cafe_name = "Coffee Time"
            settings = self.get_settings()
            if settings and 'default_cafe' in settings:
                cafe_name = settings['default_cafe']

            worksheet.append_row([
                str(next_id),
                order_date,
                delivery_date,
                str(user_id),
                cafe_name,
                items_text,
                str(total_price),
                "active"
            ])

            self.cache['orders'] = {'data': None, 'timestamp': None}
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка добавления заказа: {str(e)}", exc_info=True)
            return False

    def get_user_orders(self, user_id):
        def fetch_orders():
            if self.is_local_mode:
                return [
                    {"ID": "101", "Дата_заказа": "20.12.2024", "Состав": "Борщ x1, Котлета x1", "Сумма": "550",
                     "Статус": "active"},
                    {"ID": "98", "Дата_заказа": "19.12.2024", "Состав": "Салат Цезарь x1", "Сумма": "200",
                     "Статус": "delivered"}
                ]

            worksheet = self.get_worksheet("Заказы")
            if not worksheet:
                return []

            try:
                records = worksheet.get_all_records()
                user_orders = [order for order in records if
                               str(order.get("Сотрудник", "")).strip() == str(user_id).strip()]
                return user_orders
            except Exception as e:
                logger.error(f"❌ Ошибка получения заказов: {str(e)}", exc_info=True)
                return []

        return self._get_cached_data('orders', lambda: fetch_orders())

    def get_user_stats(self, user_id):
        orders = self.get_user_orders(user_id)

        if self.is_local_mode or not orders:
            return {
                'total_orders': len(orders),
                'last_order_date': orders[-1]['Дата_заказа'] if orders else "Нет заказов",
                'avg_price': 350,
                'favorite_dish': "Борщ",
                'top_dishes': [
                    {"name": "Борщ", "count": 8},
                    {"name": "Куриная котлета", "count": 5},
                    {"name": "Салат Цезарь", "count": 4}
                ],
                'total_spent': 5250
            }

        dish_counts = {}
        total_spent = 0
        order_dates = []

        for order in orders:
            order_dates.append(order.get("Дата_заказа", ""))
            items_text = order.get("Состав", "")

            items = items_text.split("; ")
            for item in items:
                if "x" in item:
                    try:
                        dish_part = item.split("x")[0].strip()
                        dish_name = dish_part.split(" (Цена")[0].strip()
                        dish_counts[dish_name] = dish_counts.get(dish_name, 0) + 1

                        if "(Цена:" in item:
                            price_part = item.split("(Цена:")[1].split("₽")[0].strip()
                            try:
                                total_spent += int(float(price_part))
                            except (ValueError, TypeError):
                                pass
                    except:
                        continue

        top_dishes = sorted(dish_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            'total_orders': len(orders),
            'last_order_date': order_dates[-1] if order_dates else "Нет заказов",
            'avg_price': total_spent // len(orders) if orders else 0,
            'favorite_dish': top_dishes[0][0] if top_dishes else "Нет данных",
            'top_dishes': [{"name": name, "count": count} for name, count in top_dishes],
            'total_spent': total_spent
        }

    def get_settings(self):
        def fetch_settings():
            if self.is_local_mode:
                return {
                    'order_deadline_hour': Config.ORDER_DEADLINE_HOUR,
                    'order_deadline_minute': Config.ORDER_DEADLINE_MINUTE,
                    'allowed_order_days': 1,
                    'default_cafe': "Coffee Time",
                    'default_delivery_time': "13:00-14:00"
                }

            worksheet = self.get_worksheet("Настройки")
            if not worksheet:
                return {}

            try:
                records = worksheet.get_all_records()
                settings = {}
                for record in records:
                    key = str(record.get("Ключ", "")).strip()
                    value = str(record.get("Значение", "")).strip()
                    if key and value:
                        settings[key] = value
                        if key == 'order_deadline_hour':
                            try:
                                Config.ORDER_DEADLINE_HOUR = int(value)
                            except:
                                pass
                        elif key == 'order_deadline_minute':
                            try:
                                Config.ORDER_DEADLINE_MINUTE = int(value)
                            except:
                                pass
                return settings

            except Exception as e:
                logger.error(f"❌ Ошибка получения настроек: {str(e)}", exc_info=True)
                return {}

        return self._get_cached_data('settings', fetch_settings)

    def is_user_registered(self, user_id):
        employees = self.get_employees()
        return any(str(emp.get("Telegram ID", "")).strip() == str(user_id).strip() for emp in employees)

    def register_user(self, user_id, full_name, role="employee"):
        if self.is_local_mode:
            logger.warning(f"⚠️ [ЛОКАЛЬНЫЙ РЕЖИМ] Регистрация {user_id} ({full_name})")
            return True

        try:
            worksheet = self.get_worksheet("Сотрудники")
            if not worksheet:
                return False

            if self.is_user_registered(user_id):
                return True

            now = datetime.now(self.timezone).strftime("%Y-%m-%d")
            worksheet.append_row([str(user_id), full_name, role, "active", now])
            self.cache['employees'] = {'data': None, 'timestamp': None}
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка регистрации: {str(e)}", exc_info=True)
            return False