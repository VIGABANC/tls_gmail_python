import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse
from .watcher import run_poll_cycle, start_continuous_polling
from .utils import logger
from .storage import close_storage
from .notifier import test_connection, send_reply

app = FastAPI(title="TLScontact Gmail Watcher")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with HTML status page"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TLScontact Watcher Status</title>
        <style>
            :root {
                --primary: #2E7D32;
                --bg: #f5f5f5;
                --card-bg: #ffffff;
                --text: #333333;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background: var(--card-bg);
                padding: 2.5rem;
                border-radius: 16px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.05);
                text-align: center;
                max-width: 400px;
                width: 90%;
                border-top: 5px solid var(--primary);
            }
            .status-indicator {
                width: 15px;
                height: 15px;
                background-color: var(--primary);
                border-radius: 50%;
                display: inline-block;
                margin-right: 8px;
                box-shadow: 0 0 10px var(--primary);
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            h1 { margin: 10px 0; color: var(--primary); }
            p { color: #666; line-height: 1.6; }
            .badge {
                background: #E8F5E9;
                color: var(--primary);
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
                display: inline-block;
                margin-top: 15px;
            }
            .footer {
                margin-top: 25px;
                font-size: 0.8rem;
                color: #999;
            }
            .btn {
                display: inline-block;
                margin-top: 20px;
                padding: 10px 20px;
                background: var(--primary);
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 500;
                transition: transform 0.2s;
            }
            .btn:hover { transform: translateY(-2px); }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="status-indicator"></div>
            <h1>Watcher Online</h1>
            <p>The TLScontact Gmail Watcher service is running and monitoring your inbox for appointment updates.</p>
            <div class="badge">Healthy & Monitoring</div>
            <div style="margin-top: 20px;">
                <a href="/test-telegram" class="btn">Test Telegram Notification</a>
            </div>
            <div class="footer">
                FastAPI • Python • TLScontact Watcher
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/test-telegram")
async def trigger_test_telegram():
    """Trigger a manual Telegram status notification"""
    try:
        success = await test_connection()
        if success:
            return {"success": True, "message": "Test notification sent to Telegram"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send Telegram notification (check Railway environment variables)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Endpoint /test-telegram failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected Error: {str(e)}")

@app.get("/debug/env")
async def debug_env():
    """Check which environment variables are set (for debugging)"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    railway_env = os.getenv('RAILWAY_ENVIRONMENT')
    
    return {
        "telegram_bot_token_set": bool(bot_token),
        "telegram_bot_token_length": len(bot_token) if bot_token else 0,
        "telegram_chat_id_set": bool(chat_id),
        "telegram_chat_id_value": chat_id if chat_id else None,
        "railway_environment": railway_env,
        "is_production": bool(railway_env)
    }

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram webhook updates"""
    try:
        update = await request.json()
        logger.debug(f"Received webhook update: {update}")
        
        # Check if this is a message update
        if 'message' not in update:
            return {"ok": True}
        
        message = update['message']
        
        # Only respond to text messages
        if 'text' not in message:
            return {"ok": True}
        
        chat_id = str(message['chat']['id'])
        message_id = message['message_id']
        text = message['text']
        
        logger.info(f"Received message from {chat_id}: {text}")
        
        # Check if message is "test"
        is_test = text.lower().strip() == 'test'
        
        # Generate status response
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if is_test:
            response_text = (
                f"✅ <b>Test Received! Bot is Online.</b>\n\n"
                f"<b>Status:</b> Healthy\n"
                f"<b>Time:</b> {now}\n"
                f"<b>Environment:</b> {'Production' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}\n"
                f"<b>System:</b> Python/FastAPI monitoring TLScontact"
            )
        else:
            response_text = (
                f"🤖 <b>TLScontact Watcher</b>\n\n"
                f"I received your message: \"{text}\"\n"
                f"The service is currently online and healthy."
            )
        
        # Send reply
        await send_reply(chat_id, message_id, response_text)
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Webhook failed: {str(e)}", exc_info=True)
        # Return 200 OK even on error to prevent Telegram from retrying
        return {"ok": False, "error": str(e)}

@app.on_event("startup")
async def startup_event():
    load_dotenv()
    logger.info("Service starting...")
    
    # Start continuous polling if enabled
    if os.getenv('ENABLE_CONTINUOUS_POLL', 'false').lower() == 'true':
        asyncio.create_task(start_continuous_polling())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Service shutting down...")
    close_storage()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "tlscontact-gmail-watcher-python"
    }

@app.get("/poll")
async def poll_get():
    """Manual poll trigger endpoint (GET)"""
    try:
        logger.info("External poll trigger received (GET)")
        stats = await run_poll_cycle()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Manual poll failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/poll")
async def poll_post():
    """Manual poll trigger endpoint (POST)"""
    try:
        logger.info("Manual poll triggered via HTTP POST")
        stats = await run_poll_cycle()
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Manual poll failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', '3000'))
    uvicorn.run(app, host="0.0.0.0", port=port)
