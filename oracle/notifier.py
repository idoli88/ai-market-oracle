import urllib.parse
import requests
from oracle.config import settings
from oracle.logger import setup_logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = setup_logger(__name__)

class WhatsAppNotifier:
    def __init__(self):
        self.phone = settings.CALLMEBOT_PHONE
        self.api_key = settings.CALLMEBOT_API_KEY
        
        if not self.phone or not self.api_key:
            logger.warning("CallMeBot credentials missing. Notifications will fail.")
        else:
            logger.debug("WhatsAppNotifier initialized with credentials")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def send_message(self, message: str):
        """
        Send a WhatsApp message via CallMeBot.
        
        Args:
            message (str): The text message to send.
        """
        if not self.phone or not self.api_key:
            logger.error("Cannot send message: Missing credentials.")
            return

        # Encode message for URL
        encoded_msg = urllib.parse.quote(message)
        
        url = f"https://api.callmebot.com/whatsapp.php?phone={self.phone}&text={encoded_msg}&apikey={self.api_key}"
        
        logger.info("Sending WhatsApp message via CallMeBot")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            logger.info("WhatsApp message sent successfully.")
        else:
            # Raise exception to trigger retry
            logger.error(f"Failed to send WhatsApp message. Status: {response.status_code}")
            logger.debug(f"Response content: {response.text}")
            response.raise_for_status()
