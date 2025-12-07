from datetime import datetime, timedelta
import pytz
from config.settings import Config
import logging

logger = logging.getLogger(__name__)


def is_order_deadline_passed():
    """
    Проверяет, прошел ли дедлайн для оформления заказов.
    В тестовом режиме дедлайн отключен.
    """
    try:
        # Для тестирования отключаем дедлайн
        if Config.TEST_MODE or Config.LOCAL_MODE:
            logger.debug("🕒 Проверка дедлайна отключена в тестовом/локальном режиме")
            return False

        tz = pytz.timezone(Config.TIMEZONE)
        now = datetime.now(tz)

        # Определяем дату заказа (сегодня или завтра в зависимости от времени)
        order_date = now.date()
        if now.hour >= Config.ORDER_DEADLINE_HOUR and now.minute >= Config.ORDER_DEADLINE_MINUTE:
            order_date += timedelta(days=1)

        # Дедлайн для заказов на следующий день
        deadline = tz.localize(datetime.combine(
            order_date,
            datetime.min.time().replace(
                hour=Config.ORDER_DEADLINE_HOUR,
                minute=Config.ORDER_DEADLINE_MINUTE
            )
        ))

        logger.debug(f"🕒 Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.debug(f"🕒 Дедлайн заказа: {deadline.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.debug(f"🕒 Сравнение: now={now} > deadline={deadline} = {now > deadline}")

        return now > deadline

    except Exception as e:
        logger.error(f"❌ Ошибка проверки дедлайна: {str(e)}", exc_info=True)
        # В случае ошибки разрешаем заказы (fail-safe)
        return False


def get_next_delivery_date():
    """
    Возвращает дату ближайшей доставки (завтра или послезавтра в зависимости от дедлайна)
    """
    try:
        tz = pytz.timezone(Config.TIMEZONE)
        now = datetime.now(tz)

        # Если сейчас после дедлайна, доставка будет послезавтра
        if now.hour > Config.ORDER_DEADLINE_HOUR or (
                now.hour == Config.ORDER_DEADLINE_HOUR and now.minute >= Config.ORDER_DEADLINE_MINUTE):
            return (now + timedelta(days=2)).strftime("%Y-%m-%d")
        else:
            return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    except Exception as e:
        logger.error(f"❌ Ошибка получения даты доставки: {str(e)}")
        # В случае ошибки возвращаем завтрашнюю дату
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")