"""
Integration Tests for API Server
Run with: pytest tests/test_api_integration.py -v
"""
import itertools
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

# Configure test environment (must happen before importing application modules)
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), f"ai_market_oracle_test_{os.getpid()}.db")
os.environ.setdefault("DB_PATH", TEST_DB_PATH)
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-telegram-token")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("PASSWORD_HASH_SCHEME", "plaintext")

TEST_ADMIN_PASSWORD = "adminpass123"
# Plaintext scheme stores passwords as-is
os.environ.setdefault("ADMIN_PASSWORD_HASH", TEST_ADMIN_PASSWORD)

_ip_counter = itertools.count(1)


def _next_headers():
    """Generate headers with unique client IP for rate limiting."""
    return {"X-Forwarded-For": f"127.0.0.{next(_ip_counter)}"}

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api_server import app
from oracle import database

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """Ensure each test has an isolated database."""
    database.reset_database()
    yield


@pytest.fixture
def admin_headers():
    """Authenticate as admin and return auth headers."""
    response = client.post("/api/admin/auth", json={
        "username": "admin",
        "password": TEST_ADMIN_PASSWORD
    }, headers=_next_headers())
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_signup_success(self):
        response = client.post("/api/auth/signup", json={
            "email": f"test{os.urandom(4).hex()}@example.com",
            "password": "testpass123",
            "tickers": ["NVDA", "TSLA"]
        }, headers=_next_headers())
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_signup_weak_password(self):
        response = client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "password": "weak",
            "tickers": []
        }, headers=_next_headers())
        assert response.status_code == 422  # Validation error
    
    def test_signup_invalid_email(self):
        response = client.post("/api/auth/signup", json={
            "email": "not-an-email",
            "password": "testpass123",
            "tickers": []
        }, headers=_next_headers())
        assert response.status_code == 422
    
    def test_login_success(self):
        # First create a user
        email = f"login{os.urandom(4).hex()}@example.com"
        password = "testpass123"
        
        client.post("/api/auth/signup", json={
            "email": email,
            "password": password,
            "tickers": []
        }, headers=_next_headers())
        
        # Now login
        response = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        }, headers=_next_headers())
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_login_wrong_password(self):
        email = f"wrong{os.urandom(4).hex()}@example.com"
        
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "correct123",
            "tickers": []
        }, headers=_next_headers())
        
        response = client.post("/api/auth/login", json={
            "email": email,
            "password": "wrong123"
        }, headers=_next_headers())
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Test protected endpoints (require authentication)"""
    
    @pytest.fixture
    def auth_headers(self):
        """Create test user and return auth headers"""
        email = f"protected{os.urandom(4).hex()}@example.com"
        response = client.post("/api/auth/signup", json={
            "email": email,
            "password": "testpass123",
            "tickers": []
        }, headers=_next_headers())
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_profile_success(self, auth_headers):
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert "email" in response.json()
    
    def test_get_profile_no_auth(self):
        response = client.get("/api/auth/me")
        assert response.status_code == 403  # No auth header
    
    def test_get_subscription_status(self, auth_headers):
        response = client.get("/api/subscription/status", headers=auth_headers)
        assert response.status_code == 200
        assert "is_active" in response.json()
    
    def test_get_portfolio(self, auth_headers):
        response = client.get("/api/portfolio", headers=auth_headers)
        assert response.status_code == 200
        assert "tickers" in response.json()
    
    def test_logout_revokes_token(self, auth_headers):
        # logout
        response = client.post("/api/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        # try to use token again
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 401


class TestAdminEndpoints:
    """Test admin endpoints"""
    
    def test_admin_login_success(self):
        response = client.post("/api/admin/auth", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        }, headers=_next_headers())
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["access_token"]
    
    def test_admin_users_unauthorized(self):
        response = client.get("/api/admin/users")
        assert response.status_code == 403  # Not admin
    
    def test_admin_users_authorized(self, admin_headers):
        # Seed a user
        client.post("/api/auth/signup", json={
            "email": f"adminusers{os.urandom(4).hex()}@example.com",
            "password": "testpass123",
            "tickers": []
        }, headers=_next_headers())
        response = client.get("/api/admin/users", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_admin_analytics_unauthorized(self):
        response = client.get("/api/admin/analytics")
        assert response.status_code == 403
    
    def test_admin_analytics_authorized(self, admin_headers):
        # Seed some data
        client.post("/api/auth/signup", json={
            "email": f"adminstats{os.urandom(4).hex()}@example.com",
            "password": "testpass123",
            "tickers": ["AAPL"]
        }, headers=_next_headers())
        response = client.get("/api/admin/analytics", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        assert "total_users" in body


class TestRateLimiting:
    """Test rate limiting"""
    
    def test_rate_limit_enforced(self):
        # Trigger signup more than allowed (3/hour)
        statuses = []
        same_ip_headers = {"X-Forwarded-For": "203.0.113.50"}
        for i in range(5):
            response = client.post("/api/auth/signup", json={
                "email": f"ratelimit{i}{os.urandom(2).hex()}@example.com",
                "password": "testpass123",
                "tickers": []
            }, headers=same_ip_headers)
            statuses.append(response.status_code)
        assert 429 in statuses


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
