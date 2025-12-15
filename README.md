# AI Market Oracle (SaaS MVP)

"The AI Market Oracle" is a Python-based personal market analyst agent. It monitors your stock portfolio, analyzes technical indicators and news, and sends concise, actionable insights to your Telegram via an LLM-powered bot.

## Features

*   **Smart Updates**: Sends updates 3 times a day (09:00, 14:00, 21:00).
*   **Cost Efficiency**: Uses a "Gate" logic to query the LLM only when significant events occur (Price change, RSI extreme).
*   **Telegram Bot**: Manage your portfolio (`/add`, `/remove`) and receive reports directly in Telegram.
*   **Multi-tenant**: Supports multiple users with individual portfolios.
*   **Data Sources**: 
    *   Price/Technicals: `yfinance` (MVP)
    *   Fundamentals: SEC EDGAR (Stub/Placeholder for MVP)

## Prerequisites

*   Python 3.10+
*   Docker & Docker Compose (optional)
*   Telegram Bot Token (from @BotFather)
*   OpenAI API Key

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/ai-market-oracle.git
    cd ai-market-oracle
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment:**
    Copy `.env.template` to `.env` and fill in your keys:
    ```bash
    cp .env.template .env
    ```
    
    Required variables in `.env`:
    ```ini
    OPENAI_API_KEY=sk-...
    TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
    SEC_USER_AGENT="YourAppName (admin@example.com)"
    ```

## Usage

### Running with Docker (Recommended)
```bash
docker compose up --build -d
```
This starts two services:
*   `telegram-bot`: Manages user interactions.
*   `oracle-worker`: Runs the analysis pipeline on a schedule (09:00, 14:00, 21:00).

### User Management (Admin)
Use the CLI to manage subscribers manually:

```bash
# Add a subscriber (Chat ID)
python manage_users.py add 123456789 --days 30

# Add a stock to user's portfolio
python manage_users.py add-ticker 123456789 NVDA

# List all subscribers
python manage_users.py list
```

### Telegram Commands
Start a chat with your bot and use:
*   `/start` - Register as a subscriber.
*   `/add TICKER` - Add a stock (e.g., `/add NVDA`).
*   `/remove TICKER` - Remove a stock.
*   `/list` - View your portfolio.
*   `/status` - Check subscription status.

## Architecture

*   **`bot.py`**: Entry point for the Telegram Bot service.
*   **`worker.py`**: Entry point for the Scheduler/Worker service.
*   **`oracle/pipeline.py`**: Core analysis logic.
*   **`oracle/database.py`**: SQLite wrapper.
*   **`oracle/analysis.py`**: The "Gate" logic.
*   **`oracle/data_source.py`**: Data fetching (yfinance).

## License
MIT
