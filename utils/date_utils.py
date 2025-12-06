from datetime import datetime
import pytz
from config.settings import Config

def is_order_deadline_passed():
    try:
        tz = pytz.timezone(Config.TIMEZONE)
        now = datetime.now(tz)
        deadline = now.replace(
            hour=Config.ORDER_DEADLINE_HOUR,
            minute=Config.ORDER_DEADLINE_MINUTE,
            second=0,
            microsecond=0
        )
        return now > deadline
    except Exception as e:
        print(f"Ошибка проверки дедлайна: {str(e)}")
        return False