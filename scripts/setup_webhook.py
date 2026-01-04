import os
import httpx
import asyncio
from dotenv import load_dotenv

async def setup_webhook():
    """Set up Telegram webhook to point to Railway deployment"""
    load_dotenv()
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env")
        return False
    
    # Get webhook URL from user or use Railway URL
    webhook_url = input("Enter your Railway app URL (e.g., https://your-app.up.railway.app): ").strip()
    
    if not webhook_url:
        print("❌ Error: Webhook URL is required")
        return False
    
    # Ensure URL ends with /webhook
    if not webhook_url.endswith('/webhook'):
        webhook_url = f"{webhook_url}/webhook"
    
    print(f"\n🔧 Setting webhook to: {webhook_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Set webhook
            url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
            response = await client.post(url, json={'url': webhook_url}, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                print("✅ Webhook set successfully!")
                print(f"   Description: {result.get('description', 'N/A')}")
                
                # Get webhook info to confirm
                info_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
                info_response = await client.get(info_url, timeout=10.0)
                info_result = info_response.json()
                
                if info_result.get('ok'):
                    webhook_info = info_result.get('result', {})
                    print(f"\n📋 Current webhook info:")
                    print(f"   URL: {webhook_info.get('url', 'N/A')}")
                    print(f"   Pending updates: {webhook_info.get('pending_update_count', 0)}")
                    
                return True
            else:
                print(f"❌ Failed: {result.get('description', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False

if __name__ == "__main__":
    print("🤖 Telegram Webhook Setup\n")
    asyncio.run(setup_webhook())
