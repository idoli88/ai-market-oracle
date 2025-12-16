"""
Tranzila Payment Gateway Integration.
Handles subscription creation, payment verification, and webhooks.
"""
import logging
import hashlib
import hmac
from typing import Dict, Optional, Any
import httpx
from datetime import datetime, timedelta

from oracle.config import settings
from oracle import database

logger = logging.getLogger(__name__)


class TranzilaClient:
    """
    Tranzila payment gateway client.
    Implements My-Billing recurring payment system.
    """
    
    BASE_URL = "https://direct.tranzila.com"
    
    def __init__(self):
        self.terminal = settings.TRANZILA_TERMINAL
        self.api_key = settings.TRANZILA_API_KEY
        self.webhook_secret = settings.TRANZILA_WEBHOOK_SECRET
    
    async def create_subscription(
        self,
        user_id: int,
        email: str,
        amount: float,
        return_url: str
    ) -> Dict[str, Any]:
        """
        Create a new subscription with Tranzila My-Billing.
        
        Args:
            user_id: Internal user ID
            email: User's email
            amount: Subscription amount (₪)
            return_url: URL to redirect after payment
        
        Returns:
            Dict with payment_url and transaction_id
        """
        try:
            # Tranzila My-Billing parameters
            params = {
                "supplier": self.terminal,
                "sum": str(amount),
                "currency": "1",  # ILS
                "cred_type": "1",  # Regular credit
                "email": email,
                "contact": email,
                "u1": str(user_id),  # Custom field for user ID
                "success_url": return_url,
                "fail_url": f"{return_url}?status=failed",
                "notify_url": f"{settings.API_HOST}:{settings.API_PORT}/api/webhooks/tranzila",
                "recurring": "1",  # Enable recurring
                "recurring_interval": "30",  # 30 days
                "recurring_sum": str(amount),
            }
            
            # Add API key authentication
            params["api_key"] = self.api_key
            
            # Create payment URL
            payment_url = f"{self.BASE_URL}/{self.terminal}?" + "&".join(
                f"{k}={v}" for k, v in params.items()
            )
            
            # Generate transaction ID (will be confirmed by webhook)
            transaction_id = f"TRZ_{user_id}_{int(datetime.now().timestamp())}"
            
            # Log pending payment
            database.log_payment(
                user_id=user_id,
                tranzila_transaction_id=transaction_id,
                amount=amount,
                status="pending",
                metadata={"email": email}
            )
            
            logger.info(f"Created Tranzila subscription for user {user_id}")
            
            return {
                "payment_url": payment_url,
                "transaction_id": transaction_id
            }
        
        except Exception as e:
            logger.error(f"Failed to create Tranzila subscription: {e}")
            raise
    
    def verify_webhook_signature(self, payload: Dict, signature: str) -> bool:
        """
        Verify Tranzila webhook signature.
        
        Args:
            payload: Webhook payload
            signature: Signature from webhook
        
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Create expected signature
            message = f"{payload.get('transaction_id')}:{payload.get('amount')}:{self.webhook_secret}"
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    async def handle_webhook(self, payload: Dict) -> bool:
        """
        Process Tranzila webhook event with retry mechanism.
        
        Args:
            payload: Webhook payload from Tranzila
        
        Returns:
            True if processed successfully, False otherwise
        """
        transaction_id = None
        
        try:
            transaction_id = payload.get("transaction_id")
            status = payload.get("Response")  # "000" = success
            amount = float(payload.get("sum", 0))
            user_id = int(payload.get("u1", 0))  # Custom field
            
            # Log webhook receipt
            logger.info(f"Processing Tranzila webhook: {transaction_id}, status: {status}, user: {user_id}")
            
            # Store webhook for audit trail
            self._log_webhook_event(payload)
            
            # Check if payment successful
            if status == "000":
                # Update payment status with retry
                success = await self._process_successful_payment(
                    transaction_id, user_id, amount
                )
                
                if success:
                    logger.info(f"Payment processed successfully for user {user_id}")
                    return True
                else:
                    # Critical: payment succeeded but we failed to activate subscription
                    self._send_critical_alert(
                        f"CRITICAL: Payment {transaction_id} succeeded but subscription activation failed for user {user_id}"
                    )
                    return False
            else:
                # Payment failed
                database.update_payment_status(transaction_id, "failed")
                logger.warning(f"Payment failed for transaction {transaction_id}: {status}")
                return False
        
        except Exception as e:
            logger.error(f"Webhook processing failed for {transaction_id}: {e}", exc_info=True)
            
            # Send alert for critical webhook failure
            self._send_critical_alert(
                f"Webhook processing exception: {transaction_id} - {str(e)}"
            )
            
            # Re-raise to trigger retry (if using async task queue)
            raise
    
    async def _process_successful_payment(
        self,
        transaction_id: str,
        user_id: int,
        amount: float,
        max_retries: int = 3
    ) -> bool:
        """
        Process successful payment with retry mechanism.
        """
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
        
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )
        async def _do_process():
            # Update payment status
            database.update_payment_status(transaction_id, "confirmed")
            
            # Activate/extend subscription
            user = database.get_user_by_id(user_id)
            if user and user.get("telegram_chat_id"):
                chat_id = user["telegram_chat_id"]
                database.add_subscriber(chat_id, days=30, plan="basic")
                logger.info(f"Activated subscription for user {user_id}")
            else:
                logger.warning(f"User {user_id} has no Telegram account linked")
            
            # Send confirmation email
            try:
                from oracle.email_service import email_service
                from datetime import datetime, timedelta
                
                end_date = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
                
                await email_service.send_payment_confirmation(
                    to_email=user["email"],
                    amount=amount,
                    transaction_id=transaction_id,
                    subscription_end_date=end_date
                )
            except Exception as email_error:
                # Email failure shouldn't fail the whole payment
                logger.error(f"Failed to send confirmation email: {email_error}")
            
            return True
        
        try:
            return await _do_process()
        except Exception as e:
            logger.error(f"Failed to process payment after {max_retries} retries: {e}")
            return False
    
    def _log_webhook_event(self, payload: Dict):
        """Log webhook event for audit trail."""
        try:
            import json
            webhook_log_file = "webhook_events.log"
            with open(webhook_log_file, "a") as f:
                f.write(f"{datetime.now().isoformat()} - {json.dumps(payload)}\n")
        except Exception as e:
            logger.error(f"Failed to log webhook event: {e}")
    
    def _send_critical_alert(self, message: str):
        """Send critical alert to admin (email/Slack/SMS)."""
        try:
            # Log to stderr for immediate visibility
            import sys
            print(f"🚨 CRITICAL ALERT: {message}", file=sys.stderr)
            
            # TODO: Send email/SMS to admin
            # TODO: Post to Slack channel
            
            # For now, just log it
            logger.critical(message)
        except Exception as e:
            logger.error(f"Failed to send critical alert: {e}")
    
    async def cancel_subscription(self, transaction_id: str) -> bool:
        """
        Cancel a recurring subscription.
        
        Args:
            transaction_id: Tranzila transaction ID
        
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            # Call Tranzila API to cancel recurring
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/cgi-bin/tranzila71u.cgi",
                    data={
                        "supplier": self.terminal,
                        "api_key": self.api_key,
                        "action": "cancel_recurring",
                        "transaction_id": transaction_id
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Cancelled subscription: {transaction_id}")
                    return True
                else:
                    logger.error(f"Failed to cancel subscription: {response.text}")
                    return False
        
        except Exception as e:
            logger.error(f"Subscription cancellation failed: {e}")
            return False


# Global client instance
tranzila_client = TranzilaClient()
