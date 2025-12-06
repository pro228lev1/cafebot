from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.google_sheets import GoogleSheetsService
from keyboards.inline_keyboards import (
    get_main_menu_keyboard,
    get_cart_keyboard,
    get_empty_cart_keyboard,
    get_back_keyboard,
    get_quantity_keyboard,
    get_confirmation_keyboard
)
from utils.date_utils import is_order_deadline_passed
from utils.safe_message_edit import safe_edit_message, safe_answer_callback

router = Router()
sheets = GoogleSheetsService()


class OrderStates(StatesGroup):
    viewing_menu = State()
    selecting_quantity = State()
    confirming_order = State()
    waiting_for_confirmation = State()


WELCOME_TEXT = "👋 Добро пожаловать в систему заказа обедов!\n\nВыберите действие:"
NOT_REGISTERED_TEXT = (
    "❌ Вы не зарегистрированы в системе!\n\n"
    "Для использования бота необходимо пройти регистрацию.\n"
    "Обратитесь к администратору для добавления в систему."
)


def format_cart_text(cart):
    """Форматирование текста корзины с расчетом итоговой стоимости"""
    if not cart:
        return "🛒 Корзина пуста!\n\nДобавьте блюда из меню.", 0

    text = "🛒 Ваша корзина:\n\n"
    total_price = 0

    for i, item in enumerate(cart, 1):
        item_price = item.get('Цена', 0) * item['quantity']
        total_price += item_price
        text += f"{i}. {item['Название']} x{item['quantity']} = {item_price}₽\n"

    text += f"\n💰 Итого к оплате: {total_price}₽\n"
    text += "\n⏳ Дедлайн заказа: 10:00 утра\n"
    text += "💬 Заказ будет доставлен завтра с 13:00 до 14:00"
    return text, total_price


async def check_user_registration(callback: CallbackQuery, state: FSMContext = None):
    """Проверка регистрации пользователя"""
    user_id = callback.from_user.id

    if not sheets.is_user_registered(user_id):
        await safe_edit_message(
            callback,
            NOT_REGISTERED_TEXT,
            None
        )
        return False

    return True


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    full_name = message.from_user.full_name

    # Автоматическая регистрация новых пользователей
    if not sheets.is_user_registered(user_id):
        sheets.register_user(user_id, full_name)
        welcome_text = (
            "✅ Вы успешно зарегистрированы!\n\n"
            "👋 Добро пожаловать в систему заказа обедов!\n"
            "Теперь вы можете оформлять заказы на обеды."
        )
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())
    else:
        await message.answer(WELCOME_TEXT, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu")
async def show_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback):
        return

    dishes = sheets.get_active_dishes()
    if not dishes:
        await safe_answer_callback(callback, "🍽 Меню временно пусто.", show_alert=True)
        return

    menu_text = "✅ Выберите блюдо:\n\n"
    for dish in dishes:
        price = dish.get('Цена', 0)
        menu_text += f"🆔 {dish['ID']} | {dish['Название']} - {price}₽\n📝 {dish['Описание']}\n\n"

    keyboard = InlineKeyboardBuilder()
    for dish in dishes:
        keyboard.button(text=f"{dish['Название']} ({dish.get('Цена', 0)}₽)", callback_data=f"select_{dish['ID']}")
    keyboard.button(text="⬅️ Назад", callback_data="back_to_main")
    keyboard.adjust(1)

    await safe_edit_message(
        callback,
        menu_text,
        keyboard.as_markup()
    )
    await state.set_state(OrderStates.viewing_menu)


@router.callback_query(F.data.startswith("select_"))
async def select_dish_quantity(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback):
        return

    dish_id = callback.data.split("_")[1]
    dishes = sheets.get_active_dishes()
    dish = next((d for d in dishes if str(d["ID"]) == dish_id), None)

    if not dish:
        await safe_answer_callback(callback, "❌ Блюдо не найдено!", show_alert=True)
        return

    # Сохраняем выбранное блюдо в состоянии
    await state.update_data(selected_dish=dish)

    # Показываем клавиатуру для выбора количества
    quantity_text = (
        f"🔢 Выберите количество для:\n"
        f"🍽 {dish['Название']}\n"
        f"💰 Цена за шт: {dish.get('Цена', 0)}₽\n\n"
        f"Выберите количество (1-10):"
    )

    await safe_edit_message(
        callback,
        quantity_text,
        get_quantity_keyboard()
    )
    await state.set_state(OrderStates.selecting_quantity)


@router.callback_query(F.data.startswith("quantity_"))
async def add_to_cart(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback):
        return

    quantity = int(callback.data.split("_")[1])
    data = await state.get_data()
    dish = data.get("selected_dish")

    if not dish:
        await safe_answer_callback(callback, "❌ Ошибка выбора блюда!", show_alert=True)
        return

    # Получаем текущую корзину
    cart = data.get("cart", [])

    # Проверяем, есть ли уже это блюдо в корзине
    existing_item = next((item for item in cart if item["ID"] == dish["ID"]), None)

    if existing_item:
        # Обновляем количество
        existing_item["quantity"] += quantity
        await safe_answer_callback(callback,
                                   f"🔄 Количество {dish['Название']} обновлено до {existing_item['quantity']} шт!",
                                   show_alert=True)
    else:
        # Добавляем новое блюдо
        cart.append({
            "ID": dish["ID"],
            "Название": dish["Название"],
            "quantity": quantity,
            "Цена": dish.get("Цена", 0),
            "Описание": dish.get("Описание", ""),
            "Кафе": dish.get("Кафе", "Coffee Time")
        })
        await safe_answer_callback(callback, f"✅ {dish['Название']} x{quantity} добавлено в корзину!", show_alert=True)

    # Обновляем корзину в состоянии
    await state.update_data(cart=cart)

    # Возвращаемся в меню
    await show_menu(callback, state)


@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery):
    if not await check_user_registration(callback):
        return

    user_id = callback.from_user.id
    orders = sheets.get_user_orders(user_id)

    if not orders:
        orders_text = "📋 История заказов пуста.\n\nУ вас еще нет оформленных заказов."
    else:
        orders_text = "📋 История ваших заказов:\n\n"
        # Берем последние 5 заказов, сортируем по дате в обратном порядке
        recent_orders = sorted(orders, key=lambda x: x.get("Дата_заказа", ""), reverse=True)[:5]

        for i, order in enumerate(recent_orders, 1):
            order_date = order.get("Дата_заказа", "Нет данных")
            items = order.get("Состав", "Нет данных")
            total_price = order.get("Сумма", "0")
            orders_text += f"{i}. Заказ от {order_date}:\n   {items}\n   💰 Сумма: {total_price}₽\n\n"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📊 Статистика", callback_data="stats")
    keyboard.button(text="⬅️ Назад", callback_data="back_to_main")
    keyboard.adjust(1)

    # Добавляем обработчик для случая, когда содержимое не изменилось
    async def on_same_content(cb: CallbackQuery):
        await safe_answer_callback(cb, "🔄 Вы уже просматриваете историю заказов", show_alert=False)

    await safe_edit_message(
        callback,
        orders_text,
        keyboard.as_markup(),
        on_same_content=on_same_content
    )

@router.callback_query(F.data == "cart")
async def show_cart(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback):
        return

    data = await state.get_data()
    cart = data.get("cart", [])

    cart_text, total_price = format_cart_text(cart)

    if not cart:
        await safe_edit_message(callback, cart_text, get_empty_cart_keyboard())
        return

    await safe_edit_message(callback, cart_text, get_cart_keyboard())
    await state.set_state(OrderStates.confirming_order)


@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback):
        return

    await state.update_data(cart=[])
    await safe_edit_message(
        callback,
        "🛒 Корзина очищена!\n\nДобавьте блюда из меню.",
        get_empty_cart_keyboard()
    )


@router.callback_query(F.data == "confirm_order")
async def confirm_order_details(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback):
        return

    if is_order_deadline_passed():
        await safe_answer_callback(callback, "⏰ Дедлайн заказа прошел! Новые заказы недоступны до завтра.",
                                   show_alert=True)
        return

    data = await state.get_data()
    cart = data.get("cart", [])

    if not cart:
        await safe_answer_callback(callback, "🛒 Корзина пуста!", show_alert=True)
        return

    cart_text, total_price = format_cart_text(cart)

    confirmation_text = (
        "📋 Подтверждение заказа:\n\n"
        f"{cart_text}\n\n"
        "📍 Адрес доставки: Офис компании\n"
        "⏰ Время доставки: 13:00-14:00\n"
        f"💰 Итоговая стоимость: {total_price}₽\n\n"
        "❓ Подтвердите оформление заказа:"
    )

    await safe_edit_message(
        callback,
        confirmation_text,
        get_confirmation_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_confirmation)


@router.callback_query(F.data == "finalize_order")
async def finalize_order(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback):
        return

    data = await state.get_data()
    cart = data.get("cart", [])

    if not cart:
        await safe_answer_callback(callback, "🛒 Корзина пуста!", show_alert=True)
        return

    user_id = callback.from_user.id
    success = sheets.add_order(user_id, cart)

    if success:
        await state.update_data(cart=[])
        order_details = (
            "🎉 Заказ успешно оформлен!\n\n"
            "📋 Детали заказа:\n"
            f"🆔 Номер заказа: {len(sheets.get_user_orders(user_id)) + 1}\n"
            f"💰 Сумма: {sum(item.get('Цена', 0) * item['quantity'] for item in cart)}₽\n"
            "⏰ Доставка: завтра с 13:00 до 14:00\n"
            "📍 Адрес: Офис компании\n\n"
            "📱 Вы получите уведомление за час до доставки.\n"
            "Спасибо за использование системы заказа обедов!"
        )
        await safe_edit_message(
            callback,
            order_details,
            get_main_menu_keyboard()
        )
    else:
        await safe_answer_callback(callback, "❌ Ошибка оформления заказа! Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    if not await check_user_registration(callback, state):
        return

    await state.clear()
    await safe_edit_message(
        callback,
        WELCOME_TEXT,
        get_main_menu_keyboard()
    )


@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "❓ Неизвестная команда\n\n"
        "Используйте меню для навигации или команду /start",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query()
async def unknown_callback(callback: CallbackQuery, state: FSMContext):
    await safe_answer_callback(callback, "❗ Неизвестное действие")
    await back_to_main(callback, state)