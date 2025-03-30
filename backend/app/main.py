import os
import uvicorn
import asyncio # For WebSocket sleep
import datetime # For timestamp
import json # For creating JSON messages
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict # For connection manager
from dotenv import load_dotenv
from ..utils.binance_client import get_current_price # Corrected relative import
# Correctly import running_bots from the bots module where it's defined
from .bots import running_bots 

# Load environment variables from .env file located in the backend directory
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- App Initialization ---
app = FastAPI(
    title="Trading Bots API",
    description="API for managing trading bots and market data.",
    version="0.1.0"
)

# --- CORS Configuration ---
# Get allowed origins from environment variables
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000") # Default if not set

origins = [
    frontend_url,
    # Add any other origins if necessary (e.g., staging environment)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # Allows all headers
)

# --- Basic Root Endpoint ---
@app.get("/", tags=["Health Check"])
async def read_root():
    """Basic health check endpoint."""
    return {"status": "API is running"}

# --- API Routers ---
from . import market, user, bots # Import the market, user, and bots routers

app.include_router(user.router, prefix="/api/user", tags=["User"]) 
app.include_router(market.router, prefix="/api/market", tags=["Market Data"]) 
app.include_router(bots.router, prefix="/api/bots", tags=["Bots"]) 

# --- WebSocket Connection Manager ---
# Simple manager for active WebSocket connections
# NOTE: This is in-memory and suitable for single-process local dev ONLY.
# For production/scaling, use Redis Pub/Sub or a dedicated message broker.
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
             self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
             print(f"Error sending personal message to {websocket.client}: {e}")
             self.disconnect(websocket) # Disconnect on send error

    async def broadcast(self, message: str):
        # Send message to all connected clients
        # Create a list of tasks for sending
        tasks = [conn.send_text(message) for conn in self.active_connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle potential errors during broadcast (e.g., client disconnected)
        # Iterate backwards to safely remove during iteration
        for i in range(len(self.active_connections) - 1, -1, -1):
            if isinstance(results[i], Exception):
                websocket = self.active_connections[i]
                print(f"Error broadcasting to {websocket.client}: {results[i]}. Disconnecting.")
                self.disconnect(websocket)


manager = ConnectionManager()

# --- WebSocket Endpoint ---
@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles WebSocket connections for real-time updates.
    - Accepts connection.
    - TODO: Implement authentication (e.g., check token sent after connection).
    - Periodically broadcasts BTCUSDT price updates and bot statuses.
    """
    await manager.connect(websocket)
    print(f"WebSocket connected: {websocket.client}") 
    try:
        await manager.send_personal_message(json.dumps({"type": "status", "message": "Connected to real-time updates."}), websocket)
        
        while True:
            # 1. Broadcast Price Update (Example: BTCUSDT)
            symbol = "BTCUSDT"
            price = await get_current_price(symbol)
            if price is not None:
                price_update_message = json.dumps({
                    "type": "price_update",
                    "symbol": symbol,
                    "price": price,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
                await manager.broadcast(price_update_message)
            else:
                 print(f"WS: Failed to get price for {symbol}, skipping broadcast.")

            # 2. Broadcast Bot Status Updates
            # Create a copy of running_bots keys to avoid issues if dict changes during iteration
            current_bot_ids = list(running_bots.keys()) 
            bot_statuses = []
            for bot_id in current_bot_ids:
                 bot_instance = running_bots.get(bot_id)
                 if bot_instance:
                     try:
                         # Assuming get_status() is synchronous
                         status_data = bot_instance.get_status() 
                         bot_statuses.append(status_data)
                     except Exception as e:
                          print(f"Error getting status for bot {bot_id}: {e}")
            
            if bot_statuses:
                 status_update_message = json.dumps({
                     "type": "bot_status_update",
                     "statuses": bot_statuses,
                     "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                 })
                 await manager.broadcast(status_update_message)


            # Wait before sending the next update cycle
            await asyncio.sleep(10) # Broadcast updates every 10 seconds

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"WebSocket disconnected: {websocket.client}") 
    except Exception as e:
         print(f"WebSocket error for {websocket.client}: {e}")
         manager.disconnect(websocket) 


# --- Main Execution Block ---
if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "127.0.0.1") # Default to localhost if not set
    port = int(os.getenv("BACKEND_PORT", 8000)) # Default to 8000 if not set
    
    print(f"Starting Uvicorn server on {host}:{port}")
    print(f"Allowing CORS origins: {origins}")
    
    # Note: reload=True is useful for development but should be False in production
    uvicorn.run("main:app", host=host, port=port, reload=True)
