from fastapi import APIRouter, HTTPException, status
import logging

# Import the utility function to get price and the client getter function
from ..utils.binance_client import get_current_price, get_binance_client 

router = APIRouter()

@router.get("/price/{symbol}", tags=["Market Data"], summary="Get current average price for a symbol")
async def get_symbol_price(symbol: str):
    """
    Retrieves the current average price for a given trading symbol from Binance Testnet.
    
    - **symbol**: The trading symbol (e.g., BTCUSDT, ETHUSDT).
    """
    # Check if client can be initialized (this performs the lazy init if needed)
    client = await get_binance_client()
    if not client:
        logging.error("Market data endpoint called but Binance client could not be initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, # Service Unavailable might be appropriate
            detail="Binance client connection is not available."
        )
        
    try:
        # Convert symbol to uppercase as required by Binance API
        symbol_upper = symbol.upper()
        price = await get_current_price(symbol_upper)
        
        if price is None:
            # This could happen if the symbol is invalid or due to an API error logged in get_current_price
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not retrieve price for symbol '{symbol_upper}'. Check symbol or Binance API status."
            )
            
        # Ensure correct dictionary formatting for JSON response
        return {"symbol": symbol_upper, "price": price} # Comma was missing here implicitly
        
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly
        raise http_exc
    except Exception as e:
        logging.error(f"Unexpected error in get_symbol_price endpoint for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching price for {symbol}."
        )

# Add more endpoints later for:
# - Historical Klines (candlestick data)
# - Order book data
# - Real-time WebSocket streams (might be handled differently)
