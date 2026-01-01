import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path to import app package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.watcher import run_poll_cycle
from app.storage import close_storage
from app.utils import logger

async def main():
    """CLI entry point for cron job (Python version)"""
    load_dotenv()
    
    try:
        logger.info('TLScontact Gmail Watcher (Python) - Starting single poll')

        stats = await run_poll_cycle()

        logger.info(f"Poll completed: {stats}")

        # Close storage connection
        close_storage()

        # Exit with success
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")

        # Close storage connection
        close_storage()

        # Exit with error code
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
