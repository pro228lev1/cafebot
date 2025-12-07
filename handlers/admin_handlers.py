from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import Config
from services.google_sheets import GoogleSheetsService

router = Router()
sheets = GoogleSheetsService()


def is_admin(user_id: int) -> bool:
    return str(user_id) == str(Config.ADMIN_TELEGRAM_ID)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!")
        return

    admin_text = (
        "👑 Панель администратора:\n\n"
        "• /toggle_dish — Активировать/деактивировать блюдо\n"
        "• /add_dish — Добавить новое блюдо (в разработке)\n\n"
        "💡 Совет: убедитесь, что таблица открыта и имеет лист «Меню» с колонками ID, Название, Активно"
    )
    await message.answer(admin_text)


@router.message(Command("toggle_dish"))
async def cmd_toggle_dish(message: Message):
    if not is_admin(message.from_user.id):
        return

    if Config.LOCAL_MODE:
        await message.answer("🚫 Админка недоступна в локальном режиме!")
        return

    try:
        dishes = sheets.get_active_dishes()
        # Получаем ВСЕ блюда (не только активные), чтобы можно было активировать неактивные
        all_dishes_raw = sheets.get_worksheet("Меню").get_all_records()
        all_dishes = []
        for d in all_dishes_raw:
            try:
                all_dishes.append({
                    "ID": str(d.get("ID", "")).strip(),
                    "Название": str(d.get("Название", "Без названия")).strip(),
                    "Активно": str(d.get("Активно", "Нет")).strip()
                })
            except:
                continue
    except Exception as e:
        await message.answer(f"⚠️ Ошибка загрузки блюд: {e}")
        return

    if not all_dishes:
        await message.answer("📋 В таблице нет блюд.")
        return

    text = "🔄 Выберите блюдо для переключения статуса:\n\n"
    for dish in all_dishes:
        status = "✅ Активно" if dish["Активно"].lower() in ("да", "yes", "1", "true") else "❌ Неактивно"
        text += f"• ID {dish['ID']}: {dish['Название']} — {status}\n"

    keyboard = InlineKeyboardBuilder()
    for dish in all_dishes:
        dish_id = dish["ID"]
        if len(dish_id) > 50:  # защита от переполнения callback_data (64 байта)
            continue
        btn_text = f"ID {dish_id}: {dish['Название']}"
        keyboard.button(text=btn_text[:30], callback_data=f"tgl_{dish_id}")  # обрезаем длинные названия

    keyboard.adjust(1)
    keyboard.row(
        InlineKeyboardBuilder()
        .button(text="⬅️ Назад", callback_data="back_to_admin")
        .as_markup()
        .inline_keyboard[0][0]
    )

    try:
        await message.answer(text + "\n👇 Нажмите на блюдо:", reply_markup=keyboard.as_markup())
    except TelegramBadRequest as e:
        await message.answer(f"❌ Ошибка отправки клавиатуры: {e}")


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    await callback.answer()
    admin_text = (
        "👑 Панель администратора:\n\n"
        "• /toggle_dish — Активировать/деактивировать блюдо\n"
        "• /add_dish — Добавить новое блюдо (в разработке)"
    )
    try:
        await callback.message.edit_text(admin_text)
    except TelegramBadRequest:
        await callback.message.answer(admin_text)


@router.callback_query(F.data.startswith("tgl_"))
async def handle_toggle_dish(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.answer("🚫 Доступ запрещён")
        return

    try:
        dish_id_str = callback.data.split("_", 1)[1]
        dish_id = int(dish_id_str)
    except (ValueError, IndexError, TypeError):
        await callback.message.answer("⚠️ Некорректный ID блюда")
        return

    try:
        success = sheets.toggle_dish_status(dish_id)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка сервера: {e}")
        return

    if success:
        status_msg = f"✅ Статус блюда ID {dish_id} изменён"
    else:
        status_msg = f"⚠️ Блюдо ID {dish_id} не найдено или ошибка обновления"

    await callback.message.answer(status_msg)

    # Обновляем список блюд
    try:
        all_dishes_raw = sheets.get_worksheet("Меню").get_all_records()
        all_dishes = []
        for d in all_dishes_raw:
            all_dishes.append({
                "ID": str(d.get("ID", "")).strip(),
                "Название": str(d.get("Название", "Без названия")).strip(),
                "Активно": str(d.get("Активно", "Нет")).strip()
            })
    except Exception as e:
        await callback.message.answer(f"⚠️ Не удалось обновить список: {e}")
        return

    text = "🔄 Текущие блюда:\n\n"
    for dish in all_dishes:
        status = "✅ Активно" if dish["Активно"].lower() in ("да", "yes", "1", "true") else "❌ Неактивно"
        text += f"• ID {dish['ID']}: {dish['Название']} — {status}\n"

    keyboard = InlineKeyboardBuilder()
    for dish in all_dishes:
        dish_id = dish["ID"]
        if len(dish_id) > 50:
            continue
        btn_text = f"ID {dish_id}: {dish['Название']}"
        keyboard.button(text=btn_text[:30], callback_data=f"tgl_{dish_id}")
    keyboard.adjust(1)
    keyboard.row(
        InlineKeyboardBuilder()
        .button(text="⬅️ Назад", callback_data="back_to_admin")
        .as_markup()
        .inline_keyboard[0][0]
    )

    try:
        await callback.message.answer(text + "\n👇 Нажмите на блюдо:", reply_markup=keyboard.as_markup())
    except TelegramBadRequest as e:
        await callback.message.answer(f"⚠️ Ошибка обновления: {e}")