from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import Config
from services.google_sheets import GoogleSheetsService

router = Router()
sheets = GoogleSheetsService()


class AdminStates(StatesGroup):
    waiting_for_dish_id = State()


def is_admin(user_id: int) -> bool:
    return user_id == Config.ADMIN_TELEGRAM_ID


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!")
        return

    admin_text = (
        "👑 Панель администратора:\n\n"
        "/toggle_dish - Активировать/деактивировать блюдо\n"
        "/add_dish - Добавить новое блюдо (в разработке)\n\n"
        "⚠️ Для работы админки укажите ADMIN_TELEGRAM_ID в .env"
    )
    await message.answer(admin_text)


@router.message(Command("toggle_dish"))
async def cmd_toggle_dish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if Config.LOCAL_MODE:
        await message.answer("🚫 Админка недоступна в локальном режиме!")
        return

    dishes = sheets.get_active_dishes()
    if not dishes:
        await message.answer("📋 Нет активных блюд для переключения!")
        return

    text = "🔄 Выберите блюдо для переключения статуса:\n\n"
    for dish in dishes:
        status = "✅ Активно" if dish["Активно"] == "Да" else "❌ Неактивно"
        text += f"ID {dish['ID']}: {dish['Название']} - {status}\n"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ Назад", callback_data="back_to_admin")

    await message.answer(text + "\n✏️ Введите ID блюда:", reply_markup=keyboard.as_markup())
    await state.set_state(AdminStates.waiting_for_dish_id)


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    admin_text = (
        "👑 Панель администратора:\n\n"
        "/toggle_dish - Активировать/деактивировать блюдо\n"
        "/add_dish - Добавить новое блюдо (в разработке)"
    )
    try:
        await callback.message.edit_text(admin_text)
    except TelegramBadRequest:
        await callback.message.answer(admin_text)


@router.message(AdminStates.waiting_for_dish_id)
async def process_dish_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    try:
        dish_id = int(message.text)
        await message.answer(f"🔧 Статус блюда ID {dish_id} изменен (в реальной версии это обновит Google Sheets)")
    except:
        await message.answer("❌ Неверный формат ID! Попробуйте еще раз.")
    finally:
        await state.clear()