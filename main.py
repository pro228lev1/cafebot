import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramServerError
)
from config.settings import Config
from handlers import user_handlers, admin_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def graceful_shutdown(bot: Bot):
    """Корректное завершение работы бота"""
    logger.info("Начинаю graceful shutdown...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.session.close()
        logger.info("Бот успешно остановлен")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")


# Исправленный обработчик ошибок
async def error_handler(event, exception):
    """Глобальный обработчик ошибок"""
    logger.error(f"Event {event} caused error: {exception}", exc_info=True)

    # Игнорируем известные не критические ошибки
    ignore_errors = [
        "message is not modified",
        "message to edit not found",
        "message can't be edited",
        "message to delete not found"
    ]

    if isinstance(exception, TelegramAPIError):
        error_str = str(exception).lower()
        if any(err in error_str for err in ignore_errors):
            logger.warning(f"Игнорируем ошибку: {exception}")
            return True

    # Обработка сетевых ошибок
    if isinstance(exception, (TelegramNetworkError, TelegramServerError)):
        logger.warning(f"Сетевая ошибка: {exception}")
        return True

    return False


async def main():
    """Основная функция запуска бота"""
    if not Config.BOT_TOKEN:
        logger.critical("❌ ОШИБКА: Не указан TELEGRAM_BOT_TOKEN в .env")
        return

    bot = Bot(token=Config.BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация роутеров
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)

    # Регистрация обработчика ошибок
    dp.errors.register(error_handler)

    # Информация о запуске
    logger.info("🚀 Бот запущен!")
    logger.info(f"🔧 Режим: {'ЛОКАЛЬНЫЙ' if Config.LOCAL_MODE else 'ПРОДАКШН'}")
    if not Config.LOCAL_MODE:
        logger.info(f"📊 Google Sheets ID: {Config.SPREADSHEET_ID}")

    # Запуск polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
    finally:
        await graceful_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот завершил работу по Ctrl+C")
    except Exception as e:
        logger.exception(f"Необработанное исключение: {e}")
        sys.exit(1)