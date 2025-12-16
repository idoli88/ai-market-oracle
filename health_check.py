#!/usr/bin/env python3
"""
Health Check Script
Verifies all critical services are running and accessible.

Usage:
    python3 health_check.py
"""
import requests
import sys
from oracle.config import settings

def check_api_health():
    """Check if API server is healthy"""
    try:
        url = f"http://{settings.API_HOST}:{settings.API_PORT}/health"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print("✅ API Server: Healthy")
            return True
        else:
            print(f"❌ API Server: Unhealthy (status {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ API Server: Unreachable ({e})")
        return False


def check_database():
    """Check if database is accessible"""
    try:
        from oracle import database
        
        # Try simple query
        database.get_user_count()
        print("✅ Database: Accessible")
        return True
    except Exception as e:
        print(f"❌ Database: Error ({e})")
        return False


def check_email_service():
    """Check if email service (AWS SES) is configured"""
    if settings.AWS_SES_FROM_EMAIL and settings.AWS_ACCESS_KEY_ID:
        print("✅ Email Service: Configured")
        return True
    else:
        print("⚠️  Email Service: Not configured")
        return False


def check_payment_gateway():
    """Check if payment gateway is configured"""
    if settings.TRANZILA_TERMINAL and settings.TRANZILA_API_KEY:
        print("✅ Payment Gateway: Configured")
        return True
    else:
        print("⚠️  Payment Gateway: Not configured")
        return False


def check_monitoring():
    """Check if monitoring (Sentry) is enabled"""
    if settings.SENTRY_DSN:
        print("✅ Monitoring: Enabled (Sentry)")
        return True
    else:
        print("⚠️  Monitoring: Disabled")
        return False


def main():
    """Run all health checks"""
    print("🔍 Running Health Checks...\n")
    
    checks = [
        check_api_health(),
        check_database(),
        check_email_service(),
        check_payment_gateway(),
        check_monitoring(),
    ]
    
    total = len(checks)
    passed = sum(1 for check in checks if check)
    
    print(f"\n📊 Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ All systems operational!")
        sys.exit(0)
    elif passed >= total - 1:
        print("⚠️  Minor issues detected")
        sys.exit(0)
    else:
        print("❌ Critical issues detected!")
        sys.exit(1)


if __name__ == "__main__":
    main()
