import os
import logging
import asyncio # Need asyncio for the lock
import uuid # Import uuid
from supabase import create_client, AsyncClient # Import from the correct package
from supabase.lib.client_options import ClientOptions # Import from the correct package path
from dotenv import load_dotenv
from typing import Optional, Dict, Any # Import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Use Service Role Key for backend operations where RLS might need bypassing
# or for operations not tied to a specific user session (e.g., admin tasks, migrations)
# WARNING: Handle the service key with extreme care. Do not expose it client-side.
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") 

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.error("Supabase URL or Service Key not found in environment variables.")
    # Raise an error or handle appropriately, as the backend client is crucial
    raise EnvironmentError("Missing Supabase URL or Service Key for backend client.")

# --- Global variable to hold the client instance ---
_supabase_backend_client: Optional[AsyncClient] = None
_client_lock = asyncio.Lock() # Lock for thread-safe initialization

async def get_supabase_backend_client() -> AsyncClient:
    """
    Lazily initializes and returns the Supabase async client instance for backend use.
    Uses the Service Role Key. Ensures thread-safe initialization.
    """
    global _supabase_backend_client
    
    if _supabase_backend_client:
        return _supabase_backend_client

    async with _client_lock:
        if _supabase_backend_client:
            return _supabase_backend_client
            
        logger.info("Initializing Supabase backend client...")
        try:
            # Using supabase-py (v2+) which includes async client
            options: ClientOptions = ClientOptions(
                # persist_session=False, # Typically false for backend service clients
                # auto_refresh_token=False 
            )
            # create_client returns both sync and async, we need AsyncClient type hint
            client: AsyncClient = create_client( 
                SUPABASE_URL, 
                SUPABASE_SERVICE_KEY, 
                options=options
            )
            _supabase_backend_client = client
            logger.info("Supabase backend client initialized successfully.")
            return _supabase_backend_client
        except Exception as e:
            logger.error(f"Failed to initialize Supabase backend client: {e}", exc_info=True)
            # Depending on the error, might want to raise it to prevent app startup
            raise RuntimeError("Could not initialize Supabase backend client.") from e

# --- Database Interaction Functions ---

async def record_trade(
    bot_config_id: uuid.UUID, 
    user_id: uuid.UUID, 
    trade_data: dict
) -> bool: # Return boolean indicating success
    """
    Records an executed trade into the 'trades' table.

    Args:
        bot_config_id (uuid.UUID): The ID of the bot configuration that executed the trade.
        user_id (uuid.UUID): The ID of the user who owns the bot.
        trade_data (dict): A dictionary containing trade details, expected keys match 
                           the 'trades' table columns (e.g., 'binance_order_id', 'symbol', 
                           'side', 'type', 'price', 'quantity', 'commission', 
                           'commission_asset', 'timestamp').
                           
    Returns:
        bool: True if recording was successful, False otherwise.
    """
    supabase = await get_supabase_backend_client()
    
    # Prepare data for insertion, ensuring required fields are present
    insert_payload = {
        "bot_config_id": str(bot_config_id),
        "user_id": str(user_id),
        "binance_order_id": trade_data.get("binance_order_id"), # Can be None
        "symbol": trade_data.get("symbol"),
        "side": trade_data.get("side"),
        "type": trade_data.get("type"),
        "price": trade_data.get("price"),
        "quantity": trade_data.get("quantity"),
        "commission": trade_data.get("commission"),
        "commission_asset": trade_data.get("commission_asset"),
        "timestamp": trade_data.get("timestamp") # Should be ISO 8601 format string or datetime object
    }

    # Validate required fields before insertion
    required_fields = ["symbol", "side", "type", "price", "quantity", "timestamp"]
    missing_fields = [field for field in required_fields if insert_payload.get(field) is None]
    if missing_fields:
        logger.error(f"Missing required fields for recording trade: {missing_fields}")
        return False # Indicate failure

    try:
        logger.info(f"Recording trade for bot {bot_config_id}: {insert_payload['side']} {insert_payload['quantity']} {insert_payload['symbol']} @ {insert_payload['price']}")
        # Use service role key implicitly via the backend client
        response = await supabase.table('trades').insert(insert_payload).execute()
        
        if response.error:
            logger.error(f"Supabase error recording trade: {response.error}")
            return False
        elif not response.data:
             logger.warning("Supabase insert for trade returned no data, but no error. Assuming success.")
             # Insert might return no data on success depending on settings
             return True
        else:
            logger.info(f"Successfully recorded trade with ID: {response.data[0].get('id')}")
            return True # Indicate success

    except Exception as e:
        logger.error(f"Unexpected error recording trade: {e}", exc_info=True)
        return False

async def record_performance_snapshot(
    bot_config_id: uuid.UUID, 
    user_id: uuid.UUID, 
    performance_data: Dict[str, Any]
) -> bool:
    """
    Records a performance snapshot into the 'performance' table.

    Args:
        bot_config_id (uuid.UUID): The ID of the bot configuration.
        user_id (uuid.UUID): The ID of the user who owns the bot.
        performance_data (Dict[str, Any]): Dictionary with performance metrics. Expected keys:
                                           'timestamp', 'total_pnl', 'total_trades', 
                                           'win_rate', 'portfolio_value', 'metrics' (jsonb).

    Returns:
        bool: True if recording was successful, False otherwise.
    """
    supabase = await get_supabase_backend_client()

    insert_payload = {
        "bot_config_id": str(bot_config_id),
        "user_id": str(user_id),
        "timestamp": performance_data.get("timestamp"), # Should be ISO 8601 or datetime
        "total_pnl": performance_data.get("total_pnl"),
        "total_trades": performance_data.get("total_trades"),
        "win_rate": performance_data.get("win_rate"),
        "portfolio_value": performance_data.get("portfolio_value"),
        "metrics": performance_data.get("metrics", {}) # Default to empty dict if not provided
    }

    # Validate required fields
    required_fields = ["timestamp", "total_pnl", "total_trades"]
    missing_fields = [field for field in required_fields if insert_payload.get(field) is None]
    if missing_fields:
        logger.error(f"Missing required fields for recording performance snapshot: {missing_fields}")
        return False

    try:
        logger.info(f"Recording performance snapshot for bot {bot_config_id} at {insert_payload['timestamp']}")
        response = await supabase.table('performance').insert(insert_payload).execute()

        if response.error:
            logger.error(f"Supabase error recording performance snapshot: {response.error}")
            return False
        elif not response.data:
             logger.warning("Supabase insert for performance snapshot returned no data, but no error. Assuming success.")
             return True
        else:
            logger.info(f"Successfully recorded performance snapshot with ID: {response.data[0].get('id')}")
            return True

    except Exception as e:
        logger.error(f"Unexpected error recording performance snapshot: {e}", exc_info=True)
        return False


# --- Example Usage (within other backend modules) ---
# async def example_db_call():
#     supabase = await get_supabase_backend_client()
#     try:
#         response = await supabase.table('your_table').select("*").eq('some_column', 'some_value').execute()
#         logger.info(f"Supabase response: {response}")
#         return response.data
#     except Exception as e:
#         logger.error(f"Error interacting with Supabase: {e}", exc_info=True)
#         return None
