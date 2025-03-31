import os
import uvicorn
import asyncio # For WebSocket sleep
import datetime # For timestamp
import json # For creating JSON messages
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status # Added HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Set, Optional # Added Optional
from dotenv import load_dotenv
from ..utils.binance_client import get_current_price # Corrected relative import
# Correctly import running_bots from the bots module where it's defined
from .bots import running_bots 
# Import JWT functions and secret
from jose import jwt, JWTError # Import JWT functions

# Load environment variables from .env file located in the backend directory
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# Load JWT Secret for WebSocket auth
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
     raise EnvironmentError("SUPABASE_JWT_SECRET environment variable not set.")

# --- App Initialization ---
app = FastAPI(
    title="Trading Bots API",
    description="API for managing trading bots and market data.",
    version="0.1.0"
)

# --- CORS Configuration ---
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000") 
origins = [ frontend_url ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# --- Basic Root Endpoint ---
@app.get("/", tags=["Health Check"])
async def read_root():
    return {"status": "API is running"}

# --- API Routers ---
from . import market, user, bots 
app.include_router(user.router, prefix="/api/user", tags=["User"]) 
app.include_router(market.router, prefix="/api/market", tags=["Market Data"]) 
app.include_router(bots.router, prefix="/api/bots", tags=["Bots"]) 

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {} 

    async def connect(self, websocket: WebSocket, user_id: str):
        # Accept is handled before calling connect
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        print(f"WebSocket connected and authenticated for user {user_id}: {websocket.client}")

    def disconnect(self, websocket: WebSocket, user_id: Optional[str] = None):
        disconnected = False
        if user_id and user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                 self.active_connections[user_id].remove(websocket)
                 if not self.active_connections[user_id]: 
                      del self.active_connections[user_id]
                 print(f"WebSocket disconnected for user {user_id}: {websocket.client}")
                 disconnected = True
        
        # Fallback if user_id wasn't provided or wasn't found above
        if not disconnected:
            for uid, connections in list(self.active_connections.items()): 
                if websocket in connections:
                    connections.remove(websocket)
                    if not connections: del self.active_connections[uid]
                    print(f"WebSocket disconnected (user {uid}): {websocket.client}")
                    disconnected = True; break
        
        if not disconnected: print(f"WebSocket {websocket.client} disconnected (user unknown or already removed).")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        # Check if connection is still open before sending
        if websocket.client_state == WebSocketState.CONNECTED:
            try: await websocket.send_text(message)
            except Exception as e: print(f"Error sending personal message to {websocket.client}: {e}"); self.disconnect(websocket) 
        else:
             print(f"Attempted to send personal message to disconnected client: {websocket.client}")
             self.disconnect(websocket) # Ensure removal if state is wrong

    async def broadcast(self, message: str):
        # Create a list of connections to send to *before* awaiting
        connections_to_send = [conn for connections in self.active_connections.values() for conn in connections if conn.client_state == WebSocketState.CONNECTED]
        if not connections_to_send: return

        tasks = [conn.send_text(message) for conn in connections_to_send]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results for errors (less critical for broadcast, just log)
        for i, result in enumerate(results):
             if isinstance(result, Exception): 
                  # We don't know exactly which connection failed without more complex tracking
                  print(f"Error during broadcast: {result}") 
                  # Disconnecting here based on index is unreliable if list changed

    async def broadcast_to_user(self, message: str, user_id: str):
        if user_id in self.active_connections:
            # Create list of connections for this user before awaiting
            user_connections = [conn for conn in self.active_connections[user_id] if conn.client_state == WebSocketState.CONNECTED]
            if not user_connections: return

            tasks = [conn.send_text(message) for conn in user_connections]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle disconnects for this specific user
            failed_connections = []
            for i, result in enumerate(results):
                 if isinstance(result, Exception):
                      failed_conn = user_connections[i]
                      print(f"Error broadcasting to user {user_id} ({failed_conn.client}): {result}. Disconnecting.")
                      failed_connections.append(failed_conn)
            
            # Disconnect failed connections for this user
            if failed_connections:
                 if user_id in self.active_connections: # Check if user still exists
                      for conn in failed_connections:
                           if conn in self.active_connections[user_id]:
                                self.active_connections[user_id].remove(conn)
                      if not self.active_connections[user_id]:
                           del self.active_connections[user_id]


manager = ConnectionManager()

# --- WebSocket Authentication Helper ---
# Import WebSocketState for connection checks
from starlette.websockets import WebSocketState 

async def authenticate_websocket(websocket: WebSocket) -> Optional[str]:
    """
    Accepts connection, waits for an auth message, validates the token, 
    and returns user_id or None if auth fails.
    """
    await websocket.accept() # Accept connection first
    try:
        message_str = await asyncio.wait_for(websocket.receive_text(), timeout=10.0) 
        message = json.loads(message_str)
        
        if message.get("type") != "auth" or not message.get("token"):
            await websocket.close(code=1008, reason="Auth message expected")
            return None
            
        token = message["token"]
        
        # --- Token Validation using JWT Secret ---
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET, 
                algorithms=["HS256"], 
                audience="authenticated" 
            )
            user_id: str = payload.get("sub")
            if user_id is None: raise JWTError("Token payload missing 'sub'")
            
            print(f"WebSocket authenticated for user: {user_id} using JWT Secret.")
            return user_id

        except JWTError as e:
            print(f"WebSocket JWT Error: {e}")
            await websocket.close(code=1008, reason=f"Authentication failed: {e}")
            return None
        except Exception as e: 
             print(f"WebSocket Auth Error: {e}")
             await websocket.close(code=1008, reason="Authentication failed")
             return None
        # --- End Token Validation ---

    except asyncio.TimeoutError:
        print("WebSocket auth timeout."); await websocket.close(code=1008, reason="Auth timeout"); return None
    except WebSocketDisconnect:
         print("WebSocket disconnected before authentication."); return None 
    except json.JSONDecodeError:
         print("WebSocket received non-JSON auth message."); await websocket.close(code=1008, reason="Invalid auth message format"); return None
    except Exception as e:
        print(f"Error during WebSocket authentication: {e}"); 
        # Avoid closing if already closed
        if websocket.client_state != WebSocketState.DISCONNECTED:
             await websocket.close(code=1011, reason="Internal server error during auth")
        return None


# --- WebSocket Endpoint ---
@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    """Handles authenticated WebSocket connections for real-time updates."""
    
    user_id = await authenticate_websocket(websocket) 
    if not user_id: return 

    await manager.connect(websocket, user_id) 
    
    try:
        await manager.send_personal_message(json.dumps({"type": "status", "message": "Authenticated. Receiving updates."}), websocket)
        
        while True:
            # Check connection state before proceeding
            if websocket.client_state != WebSocketState.CONNECTED: break 

            # Example: Broadcast price update 
            symbol = "BTCUSDT"
            price = await get_current_price(symbol)
            if price is not None:
                price_update_message = json.dumps({
                    "type": "price_update", "symbol": symbol, "price": price,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
                await manager.broadcast(price_update_message) 
            
            # Example: Broadcast user-specific bot status
            # Check connection state again before potentially long operation
            if websocket.client_state != WebSocketState.CONNECTED: break 
            
            user_bot_statuses = [
                bot.get_status() for bot_id, bot in running_bots.items() 
                if bot.user_id == user_id 
            ]
            if user_bot_statuses:
                 status_update_message = json.dumps({
                     "type": "bot_status_update", "statuses": user_bot_statuses,
                     "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                 })
                 await manager.broadcast_to_user(status_update_message, user_id) 

            await asyncio.sleep(10) 

    except WebSocketDisconnect:
        print(f"WebSocket disconnected event for user {user_id} ({websocket.client})")
    except Exception as e:
         print(f"WebSocket error for user {user_id} ({websocket.client}): {e}")
    finally:
         # Ensure disconnect is called on exit
         manager.disconnect(websocket, user_id) 


# --- Main Execution Block ---
if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "127.0.0.1") 
    port = int(os.getenv("BACKEND_PORT", 8000)) 
    
    print(f"Starting Uvicorn server on {host}:{port}")
    print(f"Allowing CORS origins: {origins}")
    
    uvicorn.run("main:app", host=host, port=port, reload=True)
