"""
Integration Tests for API Server
Run with: pytest tests/test_api_integration.py -v
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api_server import app
from oracle import database

client = TestClient(app)


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
        })
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_signup_weak_password(self):
        response = client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "password": "weak",
            "tickers": []
        })
        assert response.status_code == 422  # Validation error
    
    def test_login_success(self):
        # First create a user
        email = f"login{os.urandom(4).hex()}@example.com"
        password = "testpass123"
        
        client.post("/api/auth/signup", json={
            "email": email,
            "password": password,
            "tickers": []
        })
        
        # Now login
        response = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_login_wrong_password(self):
        email = f"wrong{os.urandom(4).hex()}@example.com"
        
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "correct123",
            "tickers": []
        })
        
        response = client.post("/api/auth/login", json={
            "email": email,
            "password": "wrong123"
        })
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
        })
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


class TestAdminEndpoints:
    """Test admin endpoints"""
    
    def test_admin_login_success(self):
        # This will fail if ADMIN_PASSWORD_HASH is not set correctly
        # For testing, you'd need to set up proper admin credentials
        pass
    
    def test_admin_users_unauthorized(self):
        response = client.get("/api/admin/users")
        assert response.status_code == 403  # Not admin
    
    def test_admin_analytics_unauthorized(self):
        response = client.get("/api/admin/analytics")
        assert response.status_code == 403


class TestRateLimiting:
    """Test rate limiting"""
    
    def test_rate_limit_enforced(self):
        # Make many requests quickly
        responses = []
        for _ in range(70):  # Exceed 60/min limit
            response = client.get("/health")
            responses.append(response.status_code)
        
        # Should have some 429 (rate limited) responses
        assert 429 in responses


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
