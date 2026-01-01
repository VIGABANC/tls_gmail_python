import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from .watcher import run_poll_cycle, start_continuous_polling
from .utils import logger
from .storage import close_storage

app = FastAPI(title="TLScontact Gmail Watcher")

@app.on_event("startup")
async def startup_event():
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
