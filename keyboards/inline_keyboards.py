from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽 Меню", callback_data="menu")
    builder.button(text="🛒 Корзина", callback_data="cart")
    builder.button(text="📋 Мои заказы", callback_data="my_orders")
    builder.adjust(2)
    return builder.as_markup()


def get_cart_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для корзины (когда корзина не пуста)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оформить заказ", callback_data="confirm_order")
    builder.button(text="🗑 Очистить корзину", callback_data="clear_cart")
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_empty_cart_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пустой корзины"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽 Перейти в меню", callback_data="menu")
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой 'Назад'"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    return builder.as_markup()


def get_quantity_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора количества"""
    builder = InlineKeyboardBuilder()

    # Первая строка: 1-5
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"quantity_{i}") for i in range(1, 6)]
    builder.row(*row1)

    # Вторая строка: 6-10
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"quantity_{i}") for i in range(6, 11)]
    builder.row(*row2)

    # Третья строка: отмена
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main"))

    return builder.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения заказа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить заказ", callback_data="finalize_order")
    builder.button(text="✏️ Изменить корзину", callback_data="cart")
    builder.button(text="❌ Отменить заказ", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню админ панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽️ Меню", callback_data="admin_dishes")
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="👥 Сотрудники", callback_data="admin_employees")
    builder.button(text="📊 Отчеты", callback_data="admin_reports")
    builder.button(text="⬅️ Выход", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()


def get_admin_dishes_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления блюдами"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить блюдо", callback_data="admin_add_dish")
    builder.button(text="📋 Список блюд", callback_data="admin_list_dishes")
    builder.button(text="🗑️ Удалить блюдо", callback_data="admin_delete_dish")
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(2)
    return builder.as_markup()


def get_admin_orders_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления заказами"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Активные заказы", callback_data="admin_active_orders")
    builder.button(text="📊 Отчеты", callback_data="admin_reports")
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_employees_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления сотрудниками"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить сотрудника", callback_data="admin_add_employee")
    builder.button(text="📋 Список сотрудников", callback_data="admin_list_employees")
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_confirmation_keyboard(options, prefix="") -> InlineKeyboardMarkup:
    """Генерация клавиатуры для подтверждения с вариантами"""
    builder = InlineKeyboardBuilder()
    for option in options:
        builder.button(text=option, callback_data=f"{prefix}{option.lower()}")
    builder.button(text="❌ Отмена", callback_data="back_to_admin")
    builder.adjust(1)
    return builder.as_markup()