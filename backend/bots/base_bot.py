import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import uuid

# Import the function to get the Binance client and Optional type hint
from typing import Dict, Any, Optional
import datetime # Needed for timestamp
from ..utils.binance_client import get_binance_client, get_order_status # Added get_order_status
from ..utils.db_client import record_trade, record_performance_snapshot # Import db functions

# Configure logging for the base bot
# Each bot instance can potentially have its own logger instance later
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class BaseTradingBot(ABC):
    """
    Abstract Base Class for all trading bots.
    Defines common interface and shared functionality.
    """
    def __init__(self, bot_config: Dict[str, Any], user_id: str):
        """
        Initializes the base bot.
        
        Args:
            bot_config (Dict[str, Any]): Configuration specific to this bot instance from the database.
                                         Expected keys: 'id', 'bot_type', 'name', 'symbol', 
                                                        'is_active', 'config_params'.
            user_id (str): The Supabase user ID this bot belongs to.
        """
        self.bot_id: uuid.UUID = bot_config.get('id', uuid.uuid4()) # Get ID from config or generate one
        self.user_id: str = user_id
        self.bot_type: str = bot_config.get('bot_type', 'base')
        self.name: str = bot_config.get('name', f"{self.bot_type}_bot_{self.bot_id}")
        self.symbol: str = bot_config.get('symbol', '').upper()
        self.is_active: bool = bot_config.get('is_active', False)
        self.config_params: Dict[str, Any] = bot_config.get('config_params', {})
        
        self.logger = logging.getLogger(f"{self.bot_type}.{self.name}.{self.bot_id}")
        self.logger.setLevel(logging.INFO) # Or configure level based on global settings/config
        
        # Don't store client directly, fetch when needed via get_binance_client()
        self._run_task: Optional[asyncio.Task] = None # To hold the main execution task

        # --- Bot State ---
        self.current_position_size: float = 0.0 # Base asset quantity
        self.entry_price: Optional[float] = None # Average entry price for current position
        self.realized_pnl: float = 0.0 # Cumulative realized PnL
        self.total_trades: int = 0 # Counter for trades made by this instance
        # Add more state tracking as needed (e.g., win/loss count)

        if not self.symbol:
            self.logger.error("Bot initialized without a trading symbol.")
            raise ValueError("Trading symbol is required for bot initialization.")
            
        # Defer client check until start or action
        self.logger.info(f"Initialized bot '{self.name}' (ID: {self.bot_id}) for symbol {self.symbol}")

    @abstractmethod
    async def _run_logic(self):
        """
        The core trading logic loop specific to the bot type.
        This method must be implemented by subclasses.
        It should contain the main async loop for checking signals, placing orders, etc.
        It should also handle graceful shutdown (e.g., checking self.is_active).
        """
        pass

    async def start(self):
        """Starts the bot's main execution loop if it's marked as active and not already running."""
        if not self.is_active:
            self.logger.warning(f"Bot '{self.name}' is not active. Cannot start.")
            return
            
        if self._run_task and not self._run_task.done():
            self.logger.warning(f"Bot '{self.name}' is already running.")
            return
            
        # Check client availability before starting
        client = await get_binance_client()
        if not client:
             self.logger.error(f"Cannot start bot '{self.name}': Binance client could not be initialized.")
             return

        # TODO: Fetch initial state if needed (e.g., current position from exchange)
        # self.current_position_size = await self._fetch_current_position() 

        self.logger.info(f"Starting bot '{self.name}'...")
        self._run_task = asyncio.create_task(self._run_logic())
        self.logger.info(f"Bot '{self.name}' started successfully.")

    async def stop(self):
        """Stops the bot's main execution loop gracefully."""
        self.logger.info(f"Attempting to stop bot '{self.name}'...")
        self.is_active = False # Signal the loop to stop

        if self._run_task and not self._run_task.done():
            try:
                await asyncio.wait_for(self._run_task, timeout=10.0) 
                self.logger.info(f"Bot '{self.name}' task finished gracefully.")
            except asyncio.TimeoutError:
                self.logger.warning(f"Bot '{self.name}' task did not finish gracefully within timeout. Cancelling.")
                self._run_task.cancel()
                try: await self._run_task 
                except asyncio.CancelledError: self.logger.info(f"Bot '{self.name}' task cancelled.")
            except Exception as e:
                 self.logger.error(f"Error during bot '{self.name}' task shutdown: {e}", exc_info=True)
        else:
            self.logger.info(f"Bot '{self.name}' was not running or task already completed.")
            
        self._run_task = None 

    def update_config(self, new_config_params: Dict[str, Any]):
        """Updates the bot's configuration parameters."""
        self.logger.info(f"Updating configuration for bot '{self.name}'...")
        self.config_params.update(new_config_params)
        # TODO: Re-initialize specific params based on new_config_params if needed
        self.logger.info(f"Configuration updated: {self.config_params}")

    def get_status(self) -> Dict[str, Any]:
        """Returns the current status of the bot."""
        task_running = self._run_task is not None and not self._run_task.done()
        # TODO: Add more real-time status like current PnL, position details
        return {
            "bot_id": str(self.bot_id),
            "name": self.name,
            "type": self.bot_type,
            "symbol": self.symbol,
            "is_active": self.is_active,
            "is_running": task_running,
            "config_params": self.config_params,
            "current_position_size": self.current_position_size,
            "realized_pnl": self.realized_pnl,
            "total_trades": self.total_trades,
        }

    # --- Bot Actions ---
    
    async def _place_order(self, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Optional[Dict]:
        """Places an order via Binance client and records it."""
        client = await get_binance_client()
        if not client:
            self.logger.error("Cannot place order: Binance client not available.")
            return None
            
        self.logger.info(f"Attempting to place {side} {order_type} order for {quantity:.8f} {self.symbol} @ {price or 'Market'}")
        loop = asyncio.get_event_loop()
        try:
            order_params = { 'symbol': self.symbol, 'side': side, 'type': order_type }
            
            # Handle quantity/quoteOrderQty based on order type and side
            if order_type == 'MARKET' and side == 'BUY':
                 quote_qty = getattr(self, 'purchase_amount_quote', 0) # Used by DCA
                 if quote_qty > 0:
                     order_params['quoteOrderQty'] = quote_qty
                     self.logger.info(f"Placing MARKET BUY using quoteOrderQty: {quote_qty}")
                 else: # Fallback to base quantity if quoteOrderQty not applicable/set
                      order_params['quantity'] = quantity 
            else: # For LIMIT orders or MARKET SELLs, use base quantity
                 order_params['quantity'] = quantity

            if order_type == 'LIMIT':
                if price is None: raise ValueError("Price must be provided for LIMIT orders.")
                # TODO: Fetch symbol precision rules from exchange info
                # price_precision = 8 
                # order_params['price'] = f"{price:.{price_precision}f}" 
                order_params['price'] = str(price) # Use basic string conversion for now
                order_params['timeInForce'] = 'GTC' 
            
            # Execute the synchronous call in a thread pool
            order = await loop.run_in_executor(None, client.create_order, **order_params)
            self.logger.info(f"Order placed successfully via API: {order.get('orderId')}")
            
            # --- Update Bot State & Record Trade ---
            if order and order.get('orderId'): 
                executed_qty = float(order.get('executedQty', 0))
                
                # Basic state update (more sophisticated logic needed for partial fills, avg price)
                if executed_qty > 0:
                    self.total_trades += 1
                    if side == 'BUY':
                        # TODO: Update average entry price correctly
                        self.current_position_size += executed_qty
                        self.entry_price = float(order.get('price', 0)) if self.entry_price is None else self.entry_price # Simplistic entry price
                    elif side == 'SELL':
                         # TODO: Calculate realized PnL correctly
                         if self.entry_price:
                              self.realized_pnl += (float(order.get('price', 0)) - self.entry_price) * executed_qty
                         self.current_position_size -= executed_qty
                         if self.current_position_size < 1e-9: # Handle float precision
                              self.current_position_size = 0.0
                              self.entry_price = None # Reset entry price when position is closed

                # Record in DB
                trade_details = self._parse_order_to_trade_details(order, side, order_type)
                if trade_details["quantity"] > 0:
                    await record_trade(
                        bot_config_id=self.bot_id,
                        user_id=uuid.UUID(self.user_id), 
                        trade_data=trade_details
                    )
                else:
                     self.logger.warning(f"Order {order.get('orderId')} has zero executed quantity. Not recording trade.")

            return order 
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}", exc_info=True)
            return None

    def _parse_order_to_trade_details(self, order: Dict, side: str, order_type: str) -> Dict:
        """Helper to extract trade details from a Binance order response."""
        # Default timestamp to now if transactTime is missing (shouldn't happen often)
        timestamp_ms = order.get('transactTime', datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        timestamp_iso = datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc).isoformat()
        
        executed_qty = float(order.get('executedQty', 0))
        price = float(order.get('price', 0)) if order.get('price') else None
        
        commission = 0.0
        commission_asset = None
        avg_fill_price = price # Use order price as default

        if order.get('fills'):
            fills = order.get('fills', [])
            commission = sum(float(fill.get('commission', 0)) for fill in fills)
            if fills: commission_asset = fills[0].get('commissionAsset')
            
            # Calculate average fill price if not explicitly set (e.g., market orders)
            if not price and fills:
                 total_cost = sum(float(f.get('price', 0)) * float(f.get('qty', 0)) for f in fills)
                 total_qty = sum(float(f.get('qty', 0)) for f in fills)
                 if total_qty > 0: avg_fill_price = total_cost / total_qty
                 else: avg_fill_price = None # Avoid division by zero

        return {
            "binance_order_id": str(order.get('orderId')),
            "symbol": order.get('symbol', self.symbol),
            "side": order.get('side', side),
            "type": order.get('type', order_type),
            "price": avg_fill_price, 
            "quantity": executed_qty,
            "commission": commission,
            "commission_asset": commission_asset,
            "timestamp": timestamp_iso
        }

    async def _get_account_balance(self, asset: str) -> Optional[Dict]:
        """Fetches account balance for a specific asset."""
        client = await get_binance_client()
        if not client:
            self.logger.error("Cannot get balance: Binance client not available.")
            return None
            
        loop = asyncio.get_event_loop()
        try:
            # Fetch balance using run_in_executor
            # Need to use lambda to pass asset correctly
            balance_data = await loop.run_in_executor(None, lambda: client.get_asset_balance(asset=asset))
            if balance_data:
                 self.logger.debug(f"Fetched balance for {asset}: {balance_data}")
                 return {
                     "asset": balance_data.get('asset'),
                     "free": float(balance_data.get('free', 0)), # Convert to float
                     "locked": float(balance_data.get('locked', 0)) # Convert to float
                 }
            else:
                 self.logger.warning(f"No balance data returned for asset {asset}.")
                 return {"asset": asset, "free": 0.0, "locked": 0.0} # Return zero balance
        except Exception as e:
            self.logger.error(f"Failed to get account balance for {asset}: {e}", exc_info=True)
            return None

    async def _update_and_record_performance(self):
        """Calculates current performance metrics and records a snapshot."""
        # --- Placeholder Performance Calculation ---
        # This needs significant refinement based on trade history and current prices
        self.logger.warning("Performance calculation logic is a placeholder.")
        
        # Fetch current price for unrealized PnL calculation
        current_price = await get_current_price(self.symbol)
        unrealized_pnl = 0.0
        if self.current_position_size > 0 and self.entry_price and current_price:
             unrealized_pnl = (current_price - self.entry_price) * self.current_position_size
        elif self.current_position_size < 0 and self.entry_price and current_price: # Handle short positions if implemented
             unrealized_pnl = (self.entry_price - current_price) * abs(self.current_position_size)
             
        # Fetch balances (Quote and Base assets)
        quote_asset = self.symbol[-4:] if self.symbol.endswith('USDT') else self.symbol[-3:] # Basic guess
        base_asset = self.symbol[:-len(quote_asset)]
        
        quote_balance_data = await self._get_account_balance(quote_asset)
        base_balance_data = await self._get_account_balance(base_asset)
        
        cash_balance = quote_balance_data['free'] if quote_balance_data else 0.0
        base_asset_value = (base_balance_data['free'] + base_balance_data['locked']) * current_price if base_balance_data and current_price else 0.0
        
        # Simplified portfolio value
        portfolio_value = cash_balance + base_asset_value 
        
        # Dummy win rate calculation (needs proper tracking)
        win_rate = 50.0 
        
        performance_data = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_pnl": self.realized_pnl + unrealized_pnl, # Combine realized and unrealized
            "total_trades": self.total_trades,
            "win_rate": win_rate, # Placeholder
            "portfolio_value": portfolio_value, # Placeholder calculation
            "metrics": { # Placeholder for more advanced metrics
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": self.realized_pnl,
                # Add Sharpe, Drawdown calculation later
            }
        }

        await record_performance_snapshot(
            bot_config_id=self.bot_id,
            user_id=uuid.UUID(self.user_id),
            performance_data=performance_data
        )

    # Add other common utilities as needed (e.g., fetching candles)
