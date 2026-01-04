import os
import httpx
from typing import Optional, Dict, Any
from .utils import logger, retry_with_backoff, is_transient_error, RateLimiter

TELEGRAM_API_BASE = 'https://api.telegram.org'

# Rate limiter: max messages per run
rate_limiter: Optional[RateLimiter] = None

def init_telegram_client():
    """Initialize Telegram client settings"""
    global rate_limiter
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        raise RuntimeError(
            'Missing Telegram credentials. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.'
        )

    # Initialize rate limiter
    max_sends = int(os.getenv('POLL_MAX_SENDS_PER_RUN', '3'))
    # Refill rate: 0.1 tokens/sec to mirror Node.js (max sends with slow refill)
    rate_limiter = RateLimiter(float(max_sends), 0.1)

    logger.info(f"Telegram client initialized. Chat ID: {chat_id}, Max sends per run: {max_sends}")

async def send_message(text: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send message to Telegram chat with retry and rate limiting"""
    options = options or {}
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        raise RuntimeError('Telegram not configured')

    # Apply rate limiting
    if rate_limiter:
        await rate_limiter.acquire(1)

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"

    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': options.get('disable_preview') != False
    }

    async def _send():
        async with httpx.AsyncClient() as client:
            logger.debug('Sending Telegram message...')
            response = await client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json()

    try:
        # Retry with backoff for transient errors
        result = await retry_with_backoff(
            _send,
            max_retries=3,
            initial_delay=1000,
            should_retry=is_transient_error
        )

        logger.info('Telegram message sent successfully')
        return result
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        
        if hasattr(e, 'response') and hasattr(e.response, 'json'):
            try:
                error_data = e.response.json()
                logger.error(f"Telegram API error: {error_data}")
            except:
                pass
        
        raise e

async def send_appointment_notification(parsed: Dict[str, Any], message_id: str):
    """Format and send appointment notification"""
    from .parser import format_for_telegram
    
    message = format_for_telegram(parsed, message_id)
    
    return await send_message(message, {
        'disable_preview': False  # Enable preview for appointment links
    })

async def test_connection() -> bool:
    """Test Telegram connection and report service status"""
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    status_msg = (
        f"✅ <b>TLScontact Watcher is Online</b>\n\n"
        f"<b>Status:</b> Healthy\n"
        f"<b>Time:</b> {now}\n"
        f"<b>Environment:</b> {'Production' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}\n"
        f"<b>System:</b> Python/FastAPI"
    )
    
    try:
        await send_message(status_msg)
        return True
    except Exception as e:
        logger.error(f"Telegram test connection failed: {str(e)}")
        return False
