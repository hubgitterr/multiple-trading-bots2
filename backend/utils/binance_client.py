import os
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv
import logging
import asyncio
from typing import Optional, Dict # Import Dict
import pandas as pd # Import pandas at the top level

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file located in the backend directory
# Adjust the path according to the script's location relative to the .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Global variable to hold the client instance ---
_binance_client_instance: Optional[Client] = None
_client_lock = asyncio.Lock() # Lock for thread-safe initialization

async def get_binance_client() -> Optional[Client]:
    """
    Lazily initializes and returns the Binance client instance.
    Ensures thread-safe initialization.
    """
    global _binance_client_instance
    
    # Fast path: Check if already initialized without lock
    if _binance_client_instance:
        return _binance_client_instance

    async with _client_lock:
        # Double-check after acquiring lock
        if _binance_client_instance:
            return _binance_client_instance

        api_key = os.getenv("BINANCE_TESTNET_API_KEY")
        api_secret = os.getenv("BINANCE_TESTNET_API_SECRET")

        if not api_key or not api_secret:
            logging.error("Binance API Key or Secret not found in environment variables.")
            return None
        
        logging.info("Initializing Binance client...")
        try:
            client = Client(api_key, api_secret, testnet=True)
            # Test connection (optional, can be deferred further)
            # loop = asyncio.get_event_loop()
            # account_status = await loop.run_in_executor(None, client.get_account_status)
            # logging.info(f"Successfully connected to Binance Testnet. Account Status: {account_status.get('data')}")
            _binance_client_instance = client
            logging.info("Binance client initialized successfully.")
            return _binance_client_instance
            
        except BinanceAPIException as e:
            logging.error(f"Binance API Exception during initialization: {e.status_code} - {e.message}")
            return None
        except BinanceRequestException as e:
            logging.error(f"Binance Request Exception during initialization: {e.status_code} - {e.message}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during Binance client initialization: {e}", exc_info=True)
            return None

# --- Client Functions ---

async def get_current_price(symbol: str):
    """Fetches the current average price for a symbol."""
    client = await get_binance_client() # Get or initialize client
    if not client:
        logging.error("Binance client could not be initialized.")
        return None
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        # Pass symbol as a keyword argument using a lambda or functools.partial
        # Using lambda for simplicity here:
        avg_price = await loop.run_in_executor(None, lambda: client.get_avg_price(symbol=symbol))
        logging.info(f"Current average price for {symbol}: {avg_price['price']}")
        return float(avg_price['price'])
    except BinanceAPIException as e:
        logging.error(f"Binance API Error fetching price for {symbol}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching price for {symbol}: {e}", exc_info=True)
        return None

async def get_historical_klines(symbol: str, interval: str, start_str: str, end_str: str = None):
    """
    Fetches historical Klines (candlestick data) for a symbol.
    Args and Returns are the same as before.
    """
    client = await get_binance_client() # Get or initialize client
    if not client:
        logging.error("Binance client could not be initialized.")
        return None
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        logging.info(f"Fetching klines for {symbol}, interval {interval}, start {start_str}, end {end_str}")
        klines = await loop.run_in_executor(None, client.get_historical_klines, symbol, interval, start_str, end_str)
        logging.info(f"Fetched {len(klines)} klines for {symbol}")
        return klines
    except BinanceAPIException as e:
        logging.error(f"Binance API Error fetching klines for {symbol}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching klines for {symbol}: {e}", exc_info=True)
        return None

async def get_historical_klines_df(symbol: str, interval: str, start_str: str, end_str: str = None) -> Optional[pd.DataFrame]:
    """
    Fetches historical Klines and returns them as a pandas DataFrame.

    Args:
        symbol (str): Trading symbol.
        interval (str): Candlestick interval.
        start_str (str): Start date string.
        end_str (str, optional): End date string.

    Returns:
        Optional[pd.DataFrame]: DataFrame with columns like 'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                or None if an error occurs. Timestamp is set as the index.
    """
    # No need to import pandas here anymore
    
    klines = await get_historical_klines(symbol, interval, start_str, end_str)
    if klines is None:
        return None
        
    try:
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_asset_volume', 'number_of_trades', 
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        # Convert timestamp to datetime and set as index
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        # Convert relevant columns to numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume', 'number_of_trades', 
                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        # Select and return only the most common columns, or keep all? Let's keep common ones.
        df = df[['open', 'high', 'low', 'close', 'volume']] 
        
        logger.info(f"Successfully created DataFrame with {len(df)} rows for {symbol} klines.")
        return df
    except Exception as e:
        logger.error(f"Error converting klines to DataFrame for {symbol}: {e}", exc_info=True)
        return None

# --- Modify other functions similarly to use `await get_binance_client()` ---

async def get_order_status(symbol: str, order_id: str) -> Optional[Dict]:
    """Fetches the status of a specific order."""
    client = await get_binance_client()
    if not client:
        logging.error("Cannot get order status: Binance client not available.")
        return None
    
    loop = asyncio.get_event_loop()
    try:
        logging.debug(f"Fetching status for order {order_id} on {symbol}")
        # Use keyword arguments for get_order
        order_status = await loop.run_in_executor(None, lambda: client.get_order(symbol=symbol, orderId=order_id))
        return order_status
    except BinanceAPIException as e:
        # Handle specific errors, e.g., order not found (might not be an error in some cases)
        if e.code == -2013: # Error code for "Order does not exist"
             logging.warning(f"Order {order_id} on {symbol} not found on Binance.")
             return None 
        logging.error(f"Binance API Error fetching order status for {order_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching order status for {order_id}: {e}", exc_info=True)
        return None

# Add more functions here for:
# - Cancelling orders
# - Getting account balance
# - Setting up WebSocket streams (might be in a separate module)

# Example of how to use the client (if run directly, though typically imported)
# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         # Need to get client within async context now
#         client = await get_binance_client() 
#         if client:
#             price = await get_current_price("BTCUSDT")
#             if price:
#                 print(f"Retrieved BTCUSDT price: {price}")
#         else:
#             print("Could not initialize Binance client.")
#     asyncio.run(main())
