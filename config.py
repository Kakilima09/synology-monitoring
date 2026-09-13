import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///synology_monitor.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    SYNC_INTERVAL_MINUTES = int(os.environ.get('SYNC_INTERVAL_MINUTES', 5))
    SYNOLOGY_API_TIMEOUT = int(os.environ.get('SYNOLOGY_API_TIMEOUT', 30))
    WTF_CSRF_ENABLED = True
    SYNOLOGY_API_TIMEOUT = int(
        os.getenv("SYNOLOGY_API_TIMEOUT", "60")
    )

    SYNOLOGY_API_RETRIES = int(
        os.getenv("SYNOLOGY_API_RETRIES", "3")
    )

    SYNOLOGY_API_RETRY_BACKOFF = float(
        os.getenv(
            "SYNOLOGY_API_RETRY_BACKOFF",
            "1.0"
        )
    )