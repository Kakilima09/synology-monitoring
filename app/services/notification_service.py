import logging
from flask import current_app

logger = logging.getLogger(__name__)

class NotificationService:
    """Simple placeholder for future notification integrations."""
    def send_alert(self, alert):
        # In future: send email, Telegram, Slack, etc.
        logger.info(f"Alert sent: {alert.title} - {alert.message}")
        # For now, just log.
        # Could be extended with email using Flask-Mail, etc.
        pass