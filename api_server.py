"""
FastAPI Application - Main API Server
Provides REST API for landing page, authentication, subscriptions, and payments.
"""
import logging
from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Optional, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from oracle.config import settings
from oracle import database, auth
from oracle.api_schemas import (
    UserSignup, UserLogin, TokenResponse, UserProfile,
    SubscriptionStatus, CreateSubscription,
    AddTicker, PortfolioResponse,
    PaymentWebhook, InvoiceItem,
    AdminLogin, UserListItem, UpdateUserRequest, AnalyticsResponse,
    MessageResponse, ErrorResponse
)
from oracle.payments import tranzila_client
from oracle.logger import setup_logger

logger = setup_logger(__name__)

# Initialize Sentry for error tracking
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            ),
        ],
        # Capture 10% of transactions for performance monitoring
        enable_tracing=True,
    )
    logger.info("Sentry error tracking initialized")
else:
    logger.warning("Sentry not configured - error tracking disabled")

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting API server...")
    database.init_db()
    auth.check_security_settings()
    database.run_maintenance()
    yield
    logger.info("API server shutdown complete.")

# Initialize FastAPI app
app = FastAPI(
    title="AI Market Oracle API",
    description="REST API for Oracle subscription and portfolio management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTPS redirect middleware (production only)
if settings.SENTRY_ENVIRONMENT == "production":
    from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
    app.add_middleware(HTTPSRedirectMiddleware)
    logger.info("HTTPS redirect enabled (production mode)")

# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response

app.add_middleware(SecurityHeadersMiddleware)

# HTTP Bearer security
security = HTTPBearer()

# Rate limiting (respect X-Forwarded-For so tests/frontends can send client IP)
def get_client_ip(request: Request):
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_client_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- Dependency Functions ---

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current authenticated user from JWT token.
    Also checks if email is verified.
    """
    token = credentials.credentials
    user_id = auth.get_user_id_from_token(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    token_hash = auth.token_hash(token)
    if not database.is_session_active(token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked"
        )
    
    user = database.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


async def get_verified_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current authenticated AND VERIFIED user.
    Use this for protected endpoints that require email verification.
    """
    user = await get_current_user(credentials)
    
    if not user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email and verify your account."
        )
    
    return user


async def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """
    Dependency to verify admin credentials.
    """
    # For simplicity, admin uses same JWT but we check username in token
    payload = auth.verify_token(credentials.credentials)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return True


# --- Health Check ---

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# --- Authentication Endpoints ---

@app.post("/api/auth/signup", response_model=TokenResponse)
@limiter.limit("3/hour")  # Prevent bot signups
async def signup(request: Request, signup_data: UserSignup):
    """
    Create a new user account and send verification email.
    """
    try:
        # Check if user exists
        existing_user = database.get_user_by_email(signup_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        password_hash = auth.hash_password(signup_data.password)
        
        # Create user (not verified yet)
        user_id = database.create_web_user(signup_data.email, password_hash)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        # Create verification token
        verification_token = database.create_verification_token(user_id)
        if not verification_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create verification token"
            )
        
        # Send verification email
        from oracle.email_service import email_service
        base_url = f"http://{settings.API_HOST}:{settings.API_PORT}"
        
        await email_service.send_verification_email(
            to_email=signup_data.email,
            verification_token=verification_token,
            base_url=base_url
        )
        
        # Create JWT token (but user can't do much until verified)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
        token = auth.create_access_token({"sub": user_id}, expires_delta=timedelta(minutes=settings.JWT_EXPIRY_MINUTES))
        database.create_session(user_id, auth.token_hash(token), expires_at)
        
        logger.info(f"User registered (pending verification): {signup_data.email}")
        
        return TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXPIRY_MINUTES * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@app.get("/api/auth/verify-email")
async def verify_email(token: str):
    """
    Verify user's email address with token.
    """
    try:
        user_id = database.verify_email_token(token)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        logger.info(f"Email verified for user {user_id}")
        
        # Redirect to success page or return success message
        return {
            "message": "Email verified successfully! You can now use all features.",
            "success": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed"
        )


@app.post("/api/auth/resend-verification")
async def resend_verification(current_user: dict = Depends(get_current_user)):
    """
    Resend verification email to user.
    """
    try:
        if current_user.get("is_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )
        
        # Create new verification token
        verification_token = database.resend_verification_email(current_user["id"])
        if not verification_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create verification token"
            )
        
        # Send verification email
        from oracle.email_service import email_service
        base_url = f"http://{settings.API_HOST}:{settings.API_PORT}"
        
        await email_service.send_verification_email(
            to_email=current_user["email"],
            verification_token=verification_token,
            base_url=base_url
        )
        
        return MessageResponse(
            message="Verification email sent",
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend verification email"
        )


@app.post("/api/auth/login", response_model=TokenResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def login(request: Request, login_data: UserLogin):
    """
    Authenticate user and return JWT token.
    """
    try:
        # Get user
        user = database.get_user_by_email(login_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not auth.verify_password(login_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Update last login
        database.update_last_login(user["id"])
        
        # Create JWT token + session
        expires_delta = timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
        token = auth.create_access_token({"sub": user["id"]}, expires_delta=expires_delta)
        database.create_session(user["id"], auth.token_hash(token), datetime.utcnow() + expires_delta)
        
        logger.info(f"User logged in: {login_data.email}")
        
        return TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXPIRY_MINUTES * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@app.get("/api/auth/me", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user's profile.
    """
    return UserProfile(
        id=current_user["id"],
        email=current_user["email"],
        telegram_chat_id=current_user.get("telegram_chat_id"),
        created_at=current_user["created_at"],
        last_login=current_user.get("last_login")
    )


@app.post("/api/auth/logout", response_model=MessageResponse)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Revoke current JWT token.
    """
    token = credentials.credentials
    token_hash = auth.token_hash(token)
    database.deactivate_session_by_hash(token_hash)
    return MessageResponse(message="Logged out", success=True)


# --- Subscription Endpoints ---

@app.get("/api/subscription/status", response_model=SubscriptionStatus)
async def get_subscription_status(current_user: dict = Depends(get_current_user)):
    """
    Get current subscription status.
    """
    chat_id = current_user.get("telegram_chat_id")
    
    if not chat_id:
        return SubscriptionStatus(
            is_active=False,
            plan="none",
            subscription_end_date=None,
            days_remaining=None
        )
    
    status_data = database.get_subscriber_status(chat_id)
    
    if not status_data:
        return SubscriptionStatus(
            is_active=False,
            plan="none",
            subscription_end_date=None,
            days_remaining=None
        )
    
    end_date = status_data.get("subscription_end_date")
    days_remaining = None
    
    if end_date:
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)
        days_remaining = (end_date - datetime.now()).days
    
    return SubscriptionStatus(
        is_active=bool(status_data.get("is_active")),
        plan=status_data.get("plan", "basic"),
        subscription_end_date=end_date,
        days_remaining=max(0, days_remaining) if days_remaining else None
    )


@app.post("/api/subscription/create", response_model=dict)
async def create_subscription(
    subscription_data: CreateSubscription,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new subscription with Tranzila payment.
    Returns payment URL for redirect.
    """
    try:
        # Create Tranzila subscription
        return_url = subscription_data.return_url or f"{settings.API_HOST}:{settings.API_PORT}/payment-success"
        
        payment_info = await tranzila_client.create_subscription(
            user_id=current_user["id"],
            email=current_user["email"],
            amount=float(settings.SUBSCRIPTION_PRICE),
            return_url=return_url
        )
        
        return {
            "payment_url": payment_info["payment_url"],
            "transaction_id": payment_info["transaction_id"]
        }
    
    except Exception as e:
        logger.error(f"Subscription creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription"
        )


@app.post("/api/subscription/cancel", response_model=MessageResponse)
async def cancel_subscription(current_user: dict = Depends(get_current_user)):
    """
    Cancel recurring subscription.
    """
    try:
        chat_id = current_user.get("telegram_chat_id")
        
        if not chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription found"
            )
        
        # Deactivate subscriber
        database.remove_subscriber(chat_id)
        
        logger.info(f"Subscription cancelled for user {current_user['email']}")
        
        return MessageResponse(
            message="Subscription cancelled successfully",
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subscription cancellation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@app.get("/api/subscription/invoices", response_model=List[InvoiceItem])
async def get_invoices(current_user: dict = Depends(get_current_user)):
    """
    Get payment history / invoices.
    """
    try:
        payments = database.get_payment_history(current_user["id"])
        
        return [
            InvoiceItem(
                id=p["id"],
                tranzila_transaction_id=p["tranzila_transaction_id"],
                amount=p["amount"],
                currency=p["currency"],
                status=p["status"],
                created_at=p["created_at"],
                confirmed_at=p.get("confirmed_at")
            )
            for p in payments
        ]
    
    except Exception as e:
        logger.error(f"Invoice retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve invoices"
        )


# --- Portfolio Endpoints ---

@app.get("/api/portfolio", response_model=PortfolioResponse)
async def get_portfolio(current_user: dict = Depends(get_current_user)):
    """
    Get user's portfolio tickers.
    """
    chat_id = current_user.get("telegram_chat_id")
    
    if not chat_id:
        return PortfolioResponse(tickers=[], count=0)
    
    tickers = database.get_user_tickers(chat_id)
    
    return PortfolioResponse(
        tickers=tickers,
        count=len(tickers)
    )


@app.post("/api/portfolio/ticker", response_model=MessageResponse)
async def add_ticker(
    ticker_data: AddTicker,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a ticker to user's portfolio.
    """
    chat_id = current_user.get("telegram_chat_id")
    
    if not chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please link your Telegram account first"
        )
    
    success, message = database.add_ticker_to_user(chat_id, ticker_data.ticker)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return MessageResponse(message=message, success=True)


@app.delete("/api/portfolio/ticker/{ticker}", response_model=MessageResponse)
async def remove_ticker(
    ticker: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a ticker from user's portfolio.
    """
    chat_id = current_user.get("telegram_chat_id")
    
    if not chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please link your Telegram account first"
        )
    
    success = database.remove_ticker_from_user(chat_id, ticker.upper())
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove ticker"
        )
    
    return MessageResponse(
        message=f"Removed {ticker.upper()} from portfolio",
        success=True
    )


# --- Payment Webhooks ---

@app.post("/api/webhooks/tranzila")
async def tranzila_webhook(payload: dict):
    """
    Handle Tranzila payment webhook.
    """
    try:
        # Verify signature (if provided)
        signature = payload.get("signature")
        if signature and not tranzila_client.verify_webhook_signature(payload, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Process webhook
        success = await tranzila_client.handle_webhook(payload)
        
        if success:
            return {"status": "success"}
        else:
            return {"status": "failed"}
    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


# --- Admin Endpoints ---

@app.post("/api/admin/auth", response_model=TokenResponse)
@limiter.limit("10/minute")
async def admin_login(request: Request, login_data: AdminLogin):
    """
    Admin authentication.
    """
    if not settings.ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin password not configured"
        )
    if not auth.verify_admin_password(login_data.username, login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    
    # Create admin token
    admin_expiry = timedelta(minutes=settings.ADMIN_JWT_EXPIRY_MINUTES)
    token = auth.create_access_token({"sub": "admin", "role": "admin"}, expires_delta=admin_expiry)
    
    logger.info("Admin logged in")
    
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60
    )


@app.get("/api/admin/users", response_model=List[UserListItem])
async def get_all_users(
    limit: int = 100,
    offset: int = 0,
    _: bool = Depends(verify_admin)
):
    """
    Get all users (admin only).
    """
    users = database.get_all_web_users(limit, offset)
    
    return [
        UserListItem(
            id=u["id"],
            email=u["email"],
            telegram_chat_id=u.get("telegram_chat_id"),
            is_active=bool(u.get("is_active", False)),
            plan=u.get("plan"),
            subscription_end_date=u.get("subscription_end_date"),
            created_at=u["created_at"]
        )
        for u in users
    ]


@app.get("/api/admin/analytics", response_model=AnalyticsResponse)
async def get_analytics(_: bool = Depends(verify_admin)):
    """
    Get analytics dashboard data.
    """
    try:
        total_users = database.get_user_count()
        active_subscribers = database.get_active_subscribers()
        
        # Calculate metrics
        monthly_revenue = len(active_subscribers) * settings.SUBSCRIPTION_PRICE
        
        # Get popular tickers
        all_tickers = database.get_all_unique_tickers()
        
        return AnalyticsResponse(
            total_users=total_users,
            active_subscribers=len(active_subscribers),
            monthly_revenue=float(monthly_revenue),
            churn_rate=0.0,  # TODO: Calculate actual churn rate
            popular_tickers=[{"ticker": t, "count": 0} for t in list(all_tickers)[:10]]
        )
    
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
