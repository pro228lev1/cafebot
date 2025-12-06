import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "config/google_auth.json")
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", 0))
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
    ORDER_DEADLINE_HOUR = int(os.getenv("ORDER_DEADLINE_HOUR", 10))
    ORDER_DEADLINE_MINUTE = int(os.getenv("ORDER_DEADLINE_MINUTE", 0))
    LOCAL_MODE = os.getenv("LOCAL_MODE", "False").lower() == "true"

    @classmethod
    def update_from_env(cls):
        """Обновление настроек из переменных окружения"""
        for key, value in os.environ.items():
            if key.startswith("ORDER_DEADLINE_") or key in ["TIMEZONE"]:
                setattr(cls, key, value)