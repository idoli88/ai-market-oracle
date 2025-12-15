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

### Running Locally
```bash
python main.py
```

### Running with Docker
```bash
docker-compose up -d --build
```

### Telegram Commands
Start a chat with your bot and use:
*   `/start` - Register as a subscriber.
*   `/add TICKER` - Add a stock (e.g., `/add NVDA`, `/add LUMI.TA`).
*   `/remove TICKER` - Remove a stock.
*   `/list` - View your portfolio.
*   `/status` - Check subscription status.

## Architecture

*   **`main.py`**: Orchestrates the Scheduler (threading) and the Telegram Bot (asyncio).
*   **`oracle/database.py`**: SQLite wrapper for subscriber and portfolio management.
*   **`oracle/analysis.py`**: The "Gate" logic. Decides if a stock needs an LLM summary.
*   **`oracle/data_source.py`**: Fetches market data (yfinance) and calculates Technicals (RSI/EMA).

## License
MIT
