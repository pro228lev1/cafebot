from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
import logging

logger = logging.getLogger(__name__)


async def safe_edit_message(
        callback: CallbackQuery,
        text: str,
        reply_markup=None,
        on_same_content=None
):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        # Проверяем, есть ли message у callback
        if not callback.message:
            logger.warning("Callback message is None")
            return False

        current_text = callback.message.text or ""
        current_markup = callback.message.reply_markup

        # Проверка, изменилось ли содержимое
        if (current_text.strip() == text.strip() and
                ((current_markup is None and reply_markup is None) or
                 (current_markup and reply_markup and current_markup.inline_keyboard == reply_markup.inline_keyboard))):
            if on_same_content:
                await on_same_content(callback)
            return False

        await callback.message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        error_str = str(e).lower()

        if "message is not modified" in error_str:
            logger.warning("Попытка редактирования без изменений")
            if on_same_content:
                await on_same_content(callback)
            return False
        elif "message to edit not found" in error_str or "message can't be edited" in error_str:
            logger.warning("Сообщение недоступно для редактирования, отправляем новое")
            await callback.message.answer(text, reply_markup=reply_markup)
            return False
        else:
            logger.error(f"Неизвестная ошибка редактирования: {e}")
            raise
    except Exception as e:
        logger.error(f"Критическая ошибка при редактировании: {e}")
        raise


async def safe_answer_callback(callback: CallbackQuery, text: str, show_alert: bool = False):
    """Безопасная отправка callback ответа"""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось отправить callback ответ: {e}")
    except Exception as e:
        logger.error(f"Критическая ошибка при отправке callback: {e}")