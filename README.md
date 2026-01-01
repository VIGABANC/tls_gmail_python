# TLScontact Gmail Watcher (Python Port)

A pure Python (FastAPI) port of the TLScontact Gmail Watcher. This bot monitors a Gmail inbox for appointment confirmation emails from TLScontact and extracts key details (date, location, link) to send rich notifications via Telegram.

## Features

- **Gmail Integration**: Uses OAuth2 to securely access your inbox (Read-only).
- **Smart Parsing**:
  - Detects emails from `tlscontact.com` and related domains.
  - Extracts appointment dates using `dateparser` (Support for French/English).
  - Identifies confirmation links.
- **Telegram Notifications**: Sends HTML-formatted alerts with "EMERGENCY" headers for confirmed appointments.
- **Deduplication**: Uses SQLite to track processed Message IDs, preventing duplicate alerts.
- **Resilience**:
  - Exponential backoff for network retries.
  - Rate limiting for Telegram API (max 3 messages per run).
- **Modes**:
  - **Single Run**: For Cron jobs.
  - **Server Mode**: FastAPI server with continuous background polling.

## Project Structure

```
python_backend/
├── app/
│   ├── main.py          # FastAPI server & endpoints
│   ├── watcher.py       # Core polling logic
│   ├── parser.py        # Email parsing (Regex + BeautifulSoup)
│   ├── gmail_client.py  # Google API wrapper
│   ├── notifier.py      # Telegram bot wrapper
│   ├── storage.py       # SQLite message tracking
│   └── utils.py         # Logging & helper functions
├── scripts/
│   ├── get_gmail_token.py  # OAuth2 setup script
│   └── simulate_inbox.py   # Test fixture runner
├── tests/               # Pytest suite
└── data/                # SQLite db (processed.db) location
```

## Requirements

- Python 3.11+
- Google Cloud Project with Gmail API enabled
- Telegram Bot Token

## Installation

1. **Clone & Install Dependencies**

   ```bash
   cd python_backend
   pip install -r requirements.txt
   ```

2. **Configuration**
   Copy `.env.template` to `.env` and fill in your credentials:

   ```bash
   cp .env.template .env
   ```

   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: From Google Cloud Console.
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: From @BotFather and your chat.

3. **Gmail Authentication**
   Run the helper script to generate your refresh token:

   ```bash
   python scripts/get_gmail_token.py
   ```

   Follow the prompts to authorize the app. Copy the `GOOGLE_REFRESH_TOKEN` into your `.env`.

## Usage

### Run Manually (CLI)

To run a single poll cycle (ideal for Cron):

```bash
python run_once.py
```

### Run Server (Continuous Polling)

To start the FastAPI server with background polling (if `ENABLE_CONTINUOUS_POLL=true`):

```bash
uvicorn app.main:app --reload
```

Endpoints:

- `GET /health` - Health check
- `POST /poll` - Trigger immediate poll

### Running Tests

```bash
pytest
```

Or run the fixture simulator to see how current parsers handle test emails:

```bash
python scripts/simulate_inbox.py
```

## Docker

```bash
docker build -t tls-watcher-py .
docker run -d -p 3000:3000 --env-file .env -v $(pwd)/data:/app/data tls-watcher-py
```
