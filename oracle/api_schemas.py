"""
Pydantic schemas for API request/response validation.
"""
import re
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

try:
    from email_validator import validate_email as _validate_email_external, EmailNotValidError
except ImportError:
    _validate_email_external = None
    EmailNotValidError = Exception

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    """Email validation with optional dependency, fallback to regex."""
    if _validate_email_external:
        try:
            return _validate_email_external(value).email
        except EmailNotValidError as exc:
            raise ValueError(str(exc)) from exc
    if not value or not EMAIL_REGEX.fullmatch(value):
        raise ValueError("Invalid email address")
    return value.strip().lower()


# --- Authentication Schemas ---

class UserSignup(BaseModel):
    """User signup request"""
    email: str
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    tickers: Optional[List[str]] = Field(default_factory=list, max_length=5, description="Initial tickers (max 5)")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return _validate_email(v)
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
    
    @field_validator('tickers')
    @classmethod
    def validate_tickers(cls, v):
        if v:
            return [ticker.upper().strip() for ticker in v]
        return []


class UserLogin(BaseModel):
    """User login request"""
    email: str
    password: str
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        return _validate_email(v)


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserProfile(BaseModel):
    """User profile response"""
    id: int
    email: str
    telegram_chat_id: Optional[int]
    created_at: datetime
    last_login: Optional[datetime]


# --- Subscription Schemas ---

class SubscriptionStatus(BaseModel):
    """Subscription status response"""
    is_active: bool
    plan: str
    subscription_end_date: Optional[datetime]
    days_remaining: Optional[int]


class CreateSubscription(BaseModel):
    """Create subscription request"""
    payment_method: str = "credit_card"
    return_url: Optional[str] = None


# --- Portfolio Schemas ---

class AddTicker(BaseModel):
    """Add ticker to portfolio"""
    ticker: str = Field(..., min_length=1, max_length=10)
    
    @field_validator('ticker')
    @classmethod
    def uppercase_ticker(cls, v):
        return v.upper().strip()


class PortfolioResponse(BaseModel):
    """User portfolio response"""
    tickers: List[str]
    count: int


# --- Payment Schemas ---

class PaymentWebhook(BaseModel):
    """Tranzila webhook payload"""
    transaction_id: str
    status: str
    amount: float
    currency: str = "ILS"
    user_email: str
    signature: str  # For verification
    
    @field_validator('user_email')
    @classmethod
    def validate_user_email(cls, v):
        return _validate_email(v)


class InvoiceItem(BaseModel):
    """Invoice history item"""
    id: int
    tranzila_transaction_id: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    confirmed_at: Optional[datetime]


# --- Admin Schemas ---

class AdminLogin(BaseModel):
    """Admin login request"""
    username: str
    password: str


class UserListItem(BaseModel):
    """User list item for admin dashboard"""
    id: int
    email: str
    telegram_chat_id: Optional[int]
    is_active: bool
    plan: Optional[str]
    subscription_end_date: Optional[datetime]
    created_at: datetime


class UpdateUserRequest(BaseModel):
    """Update user request (admin)"""
    subscription_days: Optional[int] = Field(None, description="Extend subscription by X days")
    plan: Optional[str] = Field(None, description="Change plan")
    is_active: Optional[bool] = Field(None, description="Activate/deactivate")


class AnalyticsResponse(BaseModel):
    """Analytics dashboard data"""
    total_users: int
    active_subscribers: int
    monthly_revenue: float
    churn_rate: float
    popular_tickers: List[dict]


# --- Generic Response Schemas ---

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str
    error_code: Optional[str] = None
