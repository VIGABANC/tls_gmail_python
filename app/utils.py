import os
import asyncio
import time
import logging
from datetime import datetime
from typing import Callable, Any, Optional

# Log levels mapping
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARNING,
    'error': logging.ERROR
}

# Configure logging
log_level_str = os.getenv('LOG_LEVEL', 'info').lower()
log_level = LOG_LEVELS.get(log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='[%(levelname)s] %(asctime)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)

logger = logging.getLogger('tlscontact-gmail-watcher')

async def sleep(ms: int):
    """Sleep utility"""
    await asyncio.sleep(ms / 1000)

async def retry_with_backoff(
    fn: Callable,
    max_retries: int = 3,
    initial_delay: int = 1000,
    max_delay: int = 30000,
    backoff_factor: int = 2,
    should_retry: Callable[[Exception], bool] = lambda e: True
) -> Any:
    """Retry an async function with exponential backoff"""
    last_error = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            
            if attempt == max_retries or not should_retry(e):
                raise e

            logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}")
            logger.info(f"Retrying in {delay}ms...")
            
            await sleep(delay)
            delay = min(delay * backoff_factor, max_delay)

    raise last_error

def is_transient_error(error: Exception) -> bool:
    """Check if error is transient (network, timeout, rate limit)"""
    if not error:
        return False
    
    msg = str(error).lower()
    
    # Common transient error keywords for httpx and other libraries
    transient_keywords = [
        'timeout', 'network', 'connection reset', 'socket hang up',
        'econnrefused', 'enotfound', 'etimedout', 'econnreset'
    ]
    
    if any(keyword in msg for keyword in transient_keywords):
        return True

    # Check for HTTP status codes if it's an HTTP error (e.g., from httpx)
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        status = error.response.status_code
        if status in [429, 500, 502, 503, 504]:
            return True

    return False

class RateLimiter:
    """Rate limiter using token bucket algorithm"""
    def __init__(self, max_tokens: float, refill_rate: float):
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()

    async def acquire(self, tokens: float = 1):
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return

        # Wait until we have enough tokens
        tokens_needed = tokens - self.tokens
        wait_time = tokens_needed / self.refill_rate
        
        await asyncio.sleep(wait_time)
        self._refill()
        self.tokens -= tokens

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now

def format_date_iso(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO 8601 string"""
    if not dt or not isinstance(dt, datetime):
        return None
    return dt.isoformat()

def escape_html(text: str) -> str:
    """Sanitize HTML for Telegram HTML mode"""
    if not text:
        return ''
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
    )
