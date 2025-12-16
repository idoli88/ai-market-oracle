# AI Market Oracle - Production SaaS Platform

**האורקל** is a production-ready SaaS platform providing personalized AI-powered market analysis via Telegram, now with full web integration for subscription management and payments.

## 🚀 New Features (Production Integration)

### Web Platform
- **Landing Page** - Beautiful, responsive signup and login
- **User Dashboard** - Manage subscription and portfolio
- **Payment Integration** - Tranzila recurring billing (₪29/month)
- **Admin Dashboard** - User management and analytics
- **Email Notifications** - AWS SES payment confirmations

### API Backend
- **20+ REST Endpoints** - Full API for web integration
- **JWT Authentication** - Secure token-based auth
- **Rate Limiting** - 60 requests/min protection
- **Comprehensive Logging** - Production-ready monitoring

---

## 📁 Project Structure

```
project/
├── api_server.py              # FastAPI backend (NEW)
├── bot.py                     # Telegram bot entry point
├── worker.py                  # Schedule worker (analysis pipeline)
├── manage_users.py            # CLI user management
│
├── oracle/                    # Core business logic
│   ├── analysis.py           # LLM-powered analysis
│   ├── data_source.py        # yfinance integration
│   ├── pipeline.py           # Analysis orchestration
│   ├── database.py           # SQLite wrapper (EXTENDED)
│   ├── telegram_bot.py       # Bot handlers
│   ├── message_formatter.py  # Telegram message templates
│   ├── auth.py               # JWT & password hashing (NEW)
│   ├── payments.py           # Tranzila integration (NEW)
│   ├── email_service.py      # AWS SES emails (NEW)
│   └── api_schemas.py        # Pydantic validation (NEW)
│
├── landing-page/             # Web frontend (UPDATED)
│   ├── index.html            # Landing + modals
│   └── app.js                # Client-side API integration (NEW)
│
├── admin-dashboard/          # Admin interface (NEW)
│   ├── index.html            # Admin UI
│   └── admin.js              # Admin logic
│
├── tests/                    # Test suite (EXTENDED)
│   ├── test_api_integration.py  # API tests (NEW)
│   └── test_*.py             # Existing tests
│
├── docker-compose.yml        # Production deployment (UPDATED)
├── requirements.txt          # Python dependencies (EXTENDED)
└── .env.template             # Configuration template (EXTENDED)
```

---

## 🎯 Quick Start

### 1. **Install Dependencies**
```bash
python3 -m pip install -r requirements.txt
```

### 2. **Configure Environment**
```bash
cp .env.template .env
# Edit .env with your keys:
# - OPENAI_API_KEY
# - TELEGRAM_BOT_TOKEN
# - JWT_SECRET_KEY (generate with: openssl rand -base64 64)
# - TRANZILA_TERMINAL, TRANZILA_API_KEY
# - AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

### 3. **Initialize Database**
```bash
python3 -c "from oracle.database import init_db; init_db()"
```

### 4. **Run Services**

**Option A: Individual Services (Development)**
```bash
# Terminal 1: API Server
python3 api_server.py

# Terminal 2: Telegram Bot
python3 bot.py

# Terminal 3: Analysis Worker
python3 worker.py
```

**Option B: Docker (Production)**
```bash
docker compose up --build
```

### 5. **Access Interfaces**

- **Landing Page**: http://localhost:8000/landing-page/index.html
- **Admin Dashboard**: http://localhost:8000/admin-dashboard/index.html
- **API Docs**: http://localhost:8000/docs (FastAPI auto-generated)
- **Health Check**: http://localhost:8000/health

---

## 💳 Payment Flow (Tranzila)

1. User signs up on website → Creates account
2. Redirected to Tranzila payment page (₪29)
3. Payment confirmed → Webhook to `/api/webhooks/tranzila`
4. System activates 30-day subscription
5. User links Telegram account → Receives analysis

**Recurring Billing**: Tranzila My-Billing handles automatic monthly renewals.

---

## 📧 Email Notifications (AWS SES)

Automated emails sent via AWS SES:
- **Payment Confirmation** - Beautiful Hebrew template
- **Receipt/Invoice** - Official payment receipt
- **Expiry Reminders** - 7 days before renewal

**Setup**: Verify domain in AWS SES before production.

---

## 👨‍💼 Admin Dashboard

Access: http://localhost:8000/admin-dashboard/index.html

**Features:**
- User management table (view all subscribers)
- Real-time analytics (users, revenue, churn)
- User detail modal (subscription, portfolio, payments)
- Manual operations (extend subscription, suspend user)

**Default Credentials** (CHANGE IN .env):
- Username: `admin`
- Password: `changeme123`

---

## 🧪 Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run API Integration Tests
```bash
pytest tests/test_api_integration.py -v
```

### Manual API Testing
```bash
# Signup
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test1234","tickers":["NVDA"]}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test1234"}'

# Get Profile (use token from login)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/auth/me
```

---

## 🌐 API Endpoints

### Public
- `GET /health` - Health check
- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `POST /api/webhooks/tranzila` - Payment webhook

### Protected (require JWT token)
- `GET /api/auth/me` - Current user profile
- `GET /api/subscription/status` - Subscription details
- `POST /api/subscription/create` - Create payment
- `POST /api/subscription/cancel` - Cancel subscription
- `GET /api/subscription/invoices` - Payment history
- `GET /api/portfolio` - User tickers
- `POST /api/portfolio/ticker` - Add ticker
- `DELETE /api/portfolio/ticker/{ticker}` - Remove ticker

### Admin (require admin JWT)
- `POST /api/admin/auth` - Admin login
- `GET /api/admin/users` - List all users
- `GET /api/admin/analytics` - Dashboard metrics

**Full API Docs**: http://localhost:8000/docs

---

## 🔐 Security

- ✅ JWT authentication with 60-min expiry
- ✅ Bcrypt password hashing (12 rounds)
- ✅ Rate limiting (60 req/min per IP)
- ✅ CORS protection
- ✅ Tranzila webhook signature verification
- ✅ SQL injection prevention (parameterized queries)
- ✅ Input validation (Pydantic schemas)
- ✅ HTTPS required in production

---

## 📦 Production Deployment

### AWS Lightsail (Recommended for MVP)

**Cost**: $10/month

```bash
# 1. Create Lightsail container service
aws lightsail create-container-service \
  --service-name oracle-mvp \
  --power micro \
  --scale 1

# 2. Push Docker image
docker build -t oracle:latest .
aws lightsail push-container-image --service-name oracle-mvp --image oracle:latest

# 3. Deploy
aws lightsail create-container-service-deployment \
  --service-name oracle-mvp \
  --containers file://lightsail-deployment.json
```

### Environment Variables (Production)
Set these in AWS console or docker-compose:
- Replace all `*_TEMPLATE` or `your_*` values
- Generate strong `JWT_SECRET_KEY`
- Use production Tranzila credentials
- Configure production AWS SES

---

## 📊 Monitoring & Logs

**CloudWatch** (if using AWS):
- Automatic logging enabled
- Set up alarms for errors

**Local Development**:
```bash
# View logs
docker compose logs -f

# View specific service
docker compose logs -f api-server
```

---

## 🛠️ Troubleshooting

**Issue**: `pip install` fails
```bash
# Use Python 3 explicitly
python3 -m pip install -r requirements.txt
```

**Issue**: Database locked
```bash
# Stop all services, then:
rm -rf subscribers.db
python3 -c "from oracle.database import init_db; init_db()"
```

**Issue**: CORS errors
```bash
# Update CORS_ORIGINS in .env
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

**Issue**: Payments not working
1. Check Tranzila credentials in `.env`
2. Verify webhook URL is accessible (use ngrok for local testing)
3. Check logs: `docker compose logs -f api-server`

---

## 📝 License

MIT

---

## 🙏 Support

For issues or questions, contact: [your-email@example.com]

---

**Built with ❤️ using FastAPI, Telegram Bot API, OpenAI GPT-4, Tranzila, and AWS**
