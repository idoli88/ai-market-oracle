"""
Pydantic schemas for API request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


# --- Authentication Schemas ---

class UserSignup(BaseModel):
    """User signup request"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    tickers: Optional[List[str]] = Field(default=[], max_items=5, description="Initial tickers (max 5)")
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
    
    @validator('tickers')
    def validate_tickers(cls, v):
        if v:
            return [ticker.upper().strip() for ticker in v]
        return []


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


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
    
    @validator('ticker')
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
