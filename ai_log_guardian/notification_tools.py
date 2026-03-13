import os
from twilio.rest import Client
import logging

logger = logging.getLogger("NotificationTools")

class NotificationTools:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.to_whatsapp = os.getenv("USER_WHATSAPP_NUMBER")
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials missing. Notifications will be logged to console only.")

    def send_whatsapp_alert(self, incident_id, container, analysis):
        """
        Sends an alert via WhatsApp.
        """
        message_body = f"""
🚨 *AI Log Guardian Alert* 🚨
*Incident ID:* {incident_id}
*Container:* {container}
*Severity:* {analysis.get('severity', 'UNKNOWN')}

*Root Cause:* {analysis.get('root_cause', 'N/A')}

*Suggested Fix:* {analysis.get('suggested_fix', 'N/A')}
        """
        
        if self.client and self.to_whatsapp:
            try:
                message = self.client.messages.create(
                    from_=f"whatsapp:{self.from_whatsapp}",
                    body=message_body,
                    to=f"whatsapp:{self.to_whatsapp}"
                )
                logger.info(f"WhatsApp notification sent: {message.sid}")
                return True
            except Exception as e:
                logger.error(f"Failed to send WhatsApp notification: {e}")
                return False
        else:
            logger.info("--- DRY RUN NOTIFICATION ---")
            logger.info(message_body)
            logger.info("---------------------------")
            return True

if __name__ == "__main__":
    # Test logic
    notifier = NotificationTools()
    notifier.send_whatsapp_alert("INC-12345", "hr-bot", {"severity": "HIGH", "root_cause": "DB Down", "suggested_fix": "Restart DB"})
