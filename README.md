# The AI Market Oracle 🔮

A "headless" investment decision support system that changes your old laptop into a 24/7 personal market analyst.
It fetches market data, analyzes it using Technical Indicators (RSI, EMA), consults an LLM (OpenAI) for a Swing Trading strategy, and notifies you via WhatsApp.

## Features
- **Watchlist**: Monitors QQQ, NVDA, TSLA, LUMI.TA by default.
- **Technical Analysis**: Calculates RSI(14), EMA(50), EMA(200).
- **AI Brain**: Uses OpenAI to interpret data with a "Swing Trader" persona.
- **Notifications**: Sends actionable advice to your WhatsApp using CallMeBot.
- **Low Resource**: Designed for legacy hardware / Docker.

## Setup

### 1. Prerequisites
- Python 3.8+
- An OpenAI API Key
- A CallMeBot API Key (Free)

### 2. Installation
```bash
# Clone the repo (or just copy the files)
cd project

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Copy the template and edit your secrets:
```bash
cp .env.template .env
nano .env
```
Fill in:
- `OPENAI_API_KEY`
- `CALLMEBOT_API_KEY`

### 4. How to get CallMeBot API Key
1. Add the phone number `+34 644 10 55 84` to your Phone Contacts. (Name it "CallMeBot")
2. Send this message: `I allow callmebot to send me messages` to the new contact created.
3. Wait until you receive the message "API Activated for your phone number. Your APIKEY is 123123"

## Managing Subscribers
Since this is a multi-tenant system, you need to add phone numbers manually to the database.

### Add a Subscriber
```bash
# Add a number for 30 days
python manage_users.py add +972501234567 --days 30
```

### List Subscribers
```bash
python manage_users.py list
```

### Remove a Subscriber
```bash
python manage_users.py remove +972501234567
```

### Docker Usage
If running in Docker, you can manage users inside the container:
```bash
docker exec -it ai_market_oracle python manage_users.py add +972501234567
```

## Usage

### Run Manually
```bash
python main.py
```

### Dry Run (Test without sending WhatsApp)
```bash
python main.py --dry-run
```

### Automation (Cron)
To run every trading day at 11:00 PM (after US close):
```bash
crontab -e
```
Add:
```
0 23 * * 1-5 /usr/bin/python3 /path/to/project/main.py >> /path/to/project/oracle.log 2>&1
```
