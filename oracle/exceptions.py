"""
Custom exception classes for better error handling.
"""

class OracleBaseException(Exception):
    """Base exception for all Oracle errors"""
    pass


class DatabaseError(OracleBaseException):
    """Database operation failed"""
    pass


class PaymentError(OracleBaseException):
    """Payment processing error"""
    pass


class PaymentWebhookError(PaymentError):
    """Webhook processing failed"""
    pass


class EmailDeliveryError(OracleBaseException):
    """Email sending failed"""
    pass


class VerificationError(OracleBaseException):
    """Email verification failed"""
    pass


class AuthenticationError(OracleBaseException):
    """Authentication failed"""
    pass


class SubscriptionError(OracleBaseException):
    """Subscription operation failed"""
    pass
