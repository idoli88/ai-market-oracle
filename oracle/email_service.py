"""
AWS SES Email Service
Sends transactional emails for payment confirmations, receipts, and notifications.
"""
import logging
from typing import Optional, Dict
import boto3
from botocore.exceptions import ClientError

from oracle.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    AWS SES email service for transactional emails.
    """
    
    def __init__(self):
        self.client = boto3.client(
            'ses',
            region_name=settings.AWS_SES_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.from_email = settings.AWS_SES_FROM_EMAIL
    
    async def send_payment_confirmation(
        self,
        to_email: str,
        amount: float,
        transaction_id: str,
        subscription_end_date: str
    ) -> bool:
        """
        Send payment confirmation email.
        
        Args:
            to_email: Recipient email
            amount: Payment amount
            transaction_id: Tranzila transaction ID
            subscription_end_date: Subscription expiry date
        
        Returns:
            True if sent successfully, False otherwise
        """
        subject = "תשלום התקבל בהצלחה - האורקל"
        
        html_body = f"""
        <!DOCTYPE html>
        <html lang="he" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Heebo', Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .header h1 {{ color: #1e40af; margin: 0; }}
                .icon {{ font-size: 48px; }}
                .content {{ margin: 20px 0; }}
                .details {{ background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .details p {{ margin: 10px 0; }}
                .amount {{ font-size: 24px; font-weight: bold; color: #10b981; }}
                .footer {{ text-align: center; margin-top: 30px; color: #6b7280; font-size: 12px; }}
                .button {{ display: inline-block; background: #1e40af; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="icon">🔮</div>
                    <h1>האורקל</h1>
                </div>
                
                <div class="content">
                    <h2>תשלום התקבל בהצלחה!</h2>
                    <p>שלום,</p>
                    <p>תודה על הצטרפותך לאורקל. המנוי שלך פעיל!</p>
                    
                    <div class="details">
                        <p><strong>סכום:</strong> <span class="amount">₪{amount:.2f}</span></p>
                        <p><strong>מספר עסקה:</strong> {transaction_id}</p>
                        <p><strong>תוקף המנוי:</strong> {subscription_end_date}</p>
                    </p>
                    </div>
                    
                    <p>כעת תקבל עדכוני שוק מותאמים אישית ישירות לטלגרם!</p>
                    
                    <p>אם עדיין לא חיברת את חשבון הטלגרם, פתח את הבוט ושלח:</p>
                    <code style="background: #f3f4f6; padding: 8px 12px; border-radius: 4px; display: inline-block;">/start</code>
                </div>
                
                <div class="footer">
                    <p>© 2025 האורקל. כל הזכויות שמורות.</p>
                    <p>מייל זה נשלח אוטומטית, אין להשיב עליו.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        האורקל - תשלום התקבל בהצלחה!
        
        שלום,
        
        תודה על הצטרפותך לאורקל. המנוי שלך פעיל!
        
        פרטי התשלום:
        סכום: ₪{amount:.2f}
        מספר עסקה: {transaction_id}
        תוקף המנוי: {subscription_end_date}
        
        כעת תקבל עדכוני שוק מותאמים אישית ישירות לטלגרם!
        
        © 2025 האורקל
        """
        
        return await self._send_email(to_email, subject, html_body, text_body)
    
    async def send_payment_receipt(
        self,
        to_email: str,
        amount: float,
        transaction_id: str,
        payment_date: str
    ) -> bool:
        """
        Send payment receipt email.
        
        Args:
            to_email: Recipient email
            amount: Payment amount
            transaction_id: Transaction ID
            payment_date: Payment date
        
        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"קבלה #{transaction_id} - האורקל"
        
        html_body = f"""
        <!DOCTYPE html>
        <html lang="he" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Heebo', Arial, sans-serif; margin: 0; padding: 20px; }}
                .receipt {{ max-width: 600px; margin: 0 auto; background: white; padding: 40px; border: 1px solid #e5e7eb; }}
                .header {{ text-align: center; margin-bottom: 40px; }}
                h1 {{ color: #1e40af; margin: 0; }}
                .receipt-number {{ color: #6b7280; margin-top: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 30px 0; }}
                th, td {{ padding: 12px; text-align: right; border-bottom: 1px solid #e5e7eb; }}
                th {{ background: #f3f4f6; font-weight: bold; }}
                .total {{ font-size: 20px; font-weight: bold; color: #1e40af; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 40px; }}
            </style>
        </head>
        <body>
            <div class="receipt">
                <div class="header">
                    <h1>🔮 האורקל</h1>
                    <div class="receipt-number">קבלה #{transaction_id}</div>
                    <p>{payment_date}</p>
                </div>
                
                <table>
                    <tr>
                        <th>תיאור</th>
                        <th>סכום</th>
                    </tr>
                    <tr>
                        <td>מנוי חודשי - האורקל</td>
                        <td>₪{amount:.2f}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="text-align: left;"><strong class="total">סה"כ: ₪{amount:.2f}</strong></td>
                    </tr>
                </table>
                
                <p>אמצעי תשלום: כרטיס אשראי</p>
                <p>מספר עסקה: {transaction_id}</p>
                
                <div class="footer">
                    <p>© 2025 האורקל | ע.מ: [COMPANY_ID]</p>
                    <p>מייל זה משמש כקבלה רשמית</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        קבלה #{transaction_id} - האורקל
        
        תאריך: {payment_date}
        
        תיאור: מנוי חודשי - האורקל
        סכום: ₪{amount:.2f}
        
        אמצעי תשלום: כרטיס אשראי
        מספר עסקה: {transaction_id}
        
        © 2025 האורקל
        """
        
        return await self._send_email(to_email, subject, html_body, text_body)
    
    async def send_subscription_expiry_reminder(
        self,
        to_email: str,
        days_remaining: int
    ) -> bool:
        """
        Send subscription expiry reminder.
        
        Args:
            to_email: Recipient email
            days_remaining: Days until expiry
        
        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"התראה: המנוי שלך יפוג בעוד {days_remaining} ימים"
        
        html_body = f"""
        <!DOCTYPE html>
        <html lang="he" dir="rtl">
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>🔔 המנוי שלך עומד לפוג</h2>
            <p>המנוי שלך לאורקל יפוג בעוד <strong>{days_remaining} ימים</strong>.</p>
            <p>המנוי יתחדש אוטומטית באמצעות אותו אמצעי תשלום.</p>
            <p>אם ברצונך לבטל, היכנס לחשבון שלך.</p>
        </body>
        </html>
        """
        
        text_body = f"המנוי שלך לאורקל יפוג בעוד {days_remaining} ימים."
        
        return await self._send_email(to_email, subject, html_body, text_body)
    
    async def send_verification_email(
        self,
        to_email: str,
        verification_token: str,
        base_url: str
    ) -> bool:
        """
        Send email verification email.
        
        Args:
            to_email: Recipient email
            verification_token: Verification token
            base_url: Base URL of the application
        
        Returns:
            True if sent successfully, False otherwise
        """
        verification_link = f"{base_url}/verify-email?token={verification_token}"
        subject = "אמת את הכתובת שלך - האורקל"
        
        html_body = f"""
        <!DOCTYPE html>
        <html lang="he" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Heebo', Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .header h1 {{ color: #1e40af; margin: 0; }}
                .icon {{ font-size: 48px; }}
                .button {{ display: inline-block; background: #1e40af; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; margin: 20px 0; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 30px; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="icon">🔮</div>
                    <h1>האורקל</h1>
                </div>
                
                <h2>ברוך הבא!</h2>
                <p>תודה שנרשמת לאורקל. כדי להשלים את ההרשמה, נא לאמת את כתובת המייל שלך.</p>
                
                <div style="text-align: center;">
                    <a href="{verification_link}" class="button">אמת כתובת מייל</a>
                </div>
                
                <p style="color: #6b7280; font-size: 14px; margin-top: 20px;">
                    או העתק את הקישור הבא לדפדפן:
                </p>
                <p style="background: #f3f4f6; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 12px;">
                    {verification_link}
                </p>
                
                <p style="color: #6b7280; font-size: 14px; margin-top: 20px;">
                    הקישור תקף ל-24 שעות.
                </p>
                
                <div class="footer">
                    <p>© 2025 האורקל. כל הזכויות שמורות.</p>
                    <p>אם לא ביקשת אימות, אין צורך לעשות כלום.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        האורקל - אימות כתובת מייל
        
        ברוך הבא!
        
        תודה שנרשמת לאורקל. כדי להשלים את ההרשמה, נא לאמת את כתובת המייל שלך.
        
        לחץ על הקישור הבא:
        {verification_link}
        
        הקישור תקף ל-24 שעות.
        
        אם לא ביקשת אימות, אין צורך לעשות כלום.
        
        © 2025 האורקל
        """
        
        return await self._send_email(to_email, subject, html_body, text_body)
    
    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """
        Internal method to send email via AWS SES.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_body: HTML body
            text_body: Plain text body
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            response = self.client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                    }
                }
            )
            
            logger.info(f"Email sent to {to_email}: {response['MessageId']}")
            return True
        
        except ClientError as e:
            logger.error(f"Failed to send email to {to_email}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False


# Global email service instance
email_service = EmailService()
