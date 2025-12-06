from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
import logging
import json

logger = logging.getLogger(__name__)


def serialize_keyboard(keyboard: InlineKeyboardMarkup) -> str:
    """Сериализация клавиатуры в строку для сравнения"""
    if keyboard is None:
        return ""
    try:
        # Преобразуем клавиатуру в JSON-строку для точного сравнения
        buttons = []
        for row in keyboard.inline_keyboard:
            row_buttons = []
            for button in row:
                button_data = {
                    'text': button.text,
                    'callback_data': button.callback_data,
                    'url': button.url,
                    'switch_inline_query': button.switch_inline_query,
                    'switch_inline_query_current_chat': button.switch_inline_query_current_chat
                }
                # Удаляем None значения для чистоты сравнения
                button_data = {k: v for k, v in button_data.items() if v is not None}
                row_buttons.append(button_data)
            buttons.append(row_buttons)
        return json.dumps(buttons, sort_keys=True)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка сериализации клавиатуры: {str(e)}")
        return ""


async def safe_edit_message(
        callback: CallbackQuery,
        text: str,
        reply_markup=None,
        on_same_content=None
):
    """Безопасное редактирование сообщения с обработкой ошибок и предотвращением дублирования"""
    try:
        # Проверяем, есть ли message у callback
        if not callback.message:
            logger.warning("Callback message is None")
            return False

        current_text = callback.message.text or ""
        current_markup = callback.message.reply_markup

        # Сравниваем тексты (игнорируем пробелы в начале и конце)
        texts_match = current_text.strip() == text.strip()

        # Сравниваем клавиатуры с помощью сериализации
        current_keyboard_str = serialize_keyboard(current_markup)
        new_keyboard_str = serialize_keyboard(reply_markup)
        keyboards_match = current_keyboard_str == new_keyboard_str

        # Если содержимое не изменилось, не редактируем сообщение
        if texts_match and keyboards_match:
            logger.debug("🔄 Сообщение не изменилось, редактирование пропущено")
            if on_same_content:
                await on_same_content(callback)
            return False

        # Пытаемся отредактировать сообщение
        await callback.message.edit_text(text, reply_markup=reply_markup)
        return True

    except TelegramBadRequest as e:
        error_str = str(e).lower()

        if "message is not modified" in error_str:
            logger.debug("🔄 Попытка редактирования без изменений (обработано)")
            if on_same_content:
                await on_same_content(callback)
            return False
        elif "message to edit not found" in error_str or "message can't be edited" in error_str:
            logger.warning("🔄 Сообщение недоступно для редактирования, отправляем новое")
            await callback.message.answer(text, reply_markup=reply_markup)
            return False
        else:
            logger.error(f"❌ Неизвестная ошибка редактирования: {e}")
            raise
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при редактировании: {e}")
        raise


async def safe_answer_callback(callback: CallbackQuery, text: str, show_alert: bool = False):
    """Безопасная отправка callback ответа"""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        error_str = str(e).lower()
        if "query is too old" in error_str or "query expired" in error_str:
            logger.debug(f"🔄 Callback query устарел: {text}")
        else:
            logger.warning(f"⚠️ Не удалось отправить callback ответ: {e}")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при отправке callback: {e}")