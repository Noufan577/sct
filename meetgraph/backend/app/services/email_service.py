import smtplib
import logging
from email.message import EmailMessage
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.server = settings.SMTP_SERVER
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM or settings.SMTP_USER

    def send_email(self, to_email: str, subject: str, content: str) -> bool:
        if not self.user or not self.password:
            logger.error("SMTP credentials not configured.")
            return False
            
        msg = EmailMessage()
        msg.set_content(content)
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = to_email

        try:
            with smtplib.SMTP(self.server, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
