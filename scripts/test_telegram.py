import asyncio
import sys
import os
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.notifier import init_telegram_client, test_connection

async def main():
    load_dotenv()
    
    print("Testing Telegram connection...")
    try:
        init_telegram_client()
        result = await test_connection()
        if result:
            print("\n[SUCCESS] Successfully sent test message! Check your Telegram chat.")
        else:
            print("\n[FAILED] Failed to send test message.")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        print("Make sure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in your .env file.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
