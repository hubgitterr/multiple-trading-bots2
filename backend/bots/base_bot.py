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
# Import Binance exceptions for specific error handling
from binance.exceptions import BinanceAPIException, BinanceOrderException

# Configure logging for the base bot
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class BaseTradingBot(ABC):
    """
    Abstract Base Class for all trading bots.
    Defines common interface and shared functionality.
    """
    def __init__(self, bot_config: Dict[str, Any], user_id: str):
        self.bot_id: uuid.UUID = bot_config.get('id', uuid.uuid4()) 
        self.user_id: str = user_id
        self.bot_type: str = bot_config.get('bot_type', 'base')
        self.name: str = bot_config.get('name', f"{self.bot_type}_bot_{self.bot_id}")
        self.symbol: str = bot_config.get('symbol', '').upper()
        self.is_active: bool = bot_config.get('is_active', False)
        self.config_params: Dict[str, Any] = bot_config.get('config_params', {})
        
        self.logger = logging.getLogger(f"{self.bot_type}.{self.name}.{self.bot_id}")
        # Set level to DEBUG to see more detailed logs during testing
        self.logger.setLevel(logging.DEBUG) 
        
        self._run_task: Optional[asyncio.Task] = None 

        # --- Bot State ---
        self.current_position_size: float = 0.0 
        self.entry_price: Optional[float] = None 
        self.realized_pnl: float = 0.0 
        self.total_trades: int = 0 

        if not self.symbol:
            self.logger.error("Bot initialized without a trading symbol.")
            raise ValueError("Trading symbol is required for bot initialization.")
            
        self.logger.info(f"Initialized bot '{self.name}' (ID: {self.bot_id}) for symbol {self.symbol}")

    @abstractmethod
    async def _run_logic(self):
        pass

    async def start(self):
        if not self.is_active:
            self.logger.warning(f"Bot '{self.name}' is not active. Cannot start.")
            return
        if self._run_task and not self._run_task.done():
            self.logger.warning(f"Bot '{self.name}' is already running.")
            return
        client = await get_binance_client()
        if not client:
             self.logger.error(f"Cannot start bot '{self.name}': Binance client could not be initialized.")
             return
        self.logger.info(f"Attempting to start bot task for '{self.name}'...")
        try:
             self._run_task = asyncio.create_task(self._run_logic_wrapper()) 
             self.logger.info(f"Bot '{self.name}' task created and background execution started.")
        except Exception as e:
             self.logger.error(f"Failed to create or start bot task for '{self.name}': {e}", exc_info=True)
             self.is_active = False 

    async def _run_logic_wrapper(self):
        self.logger.info(f"Bot '{self.name}' _run_logic task starting execution.")
        try:
            await self._run_logic()
        except asyncio.CancelledError:
             self.logger.info(f"Bot '{self.name}' task explicitly cancelled.")
        except Exception as e:
            self.logger.error(f"Unhandled exception in _run_logic for bot '{self.name}': {e}", exc_info=True)
            self.is_active = False 
        finally:
             self.logger.info(f"Bot '{self.name}' _run_logic task finished execution (is_active: {self.is_active}).")

    async def stop(self):
        self.logger.info(f"Attempting to stop bot '{self.name}'...")
        self.is_active = False 
        if self._run_task and not self._run_task.done():
            try:
                await asyncio.wait_for(self._run_task, timeout=15.0) 
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
        self.logger.info(f"Updating configuration for bot '{self.name}'...")
        self.config_params.update(new_config_params)
        self.logger.info(f"Configuration updated: {self.config_params}")

    def get_status(self) -> Dict[str, Any]:
        task_running = self._run_task is not None and not self._run_task.done()
        return {
            "bot_id": str(self.bot_id), "name": self.name, "type": self.bot_type,
            "symbol": self.symbol, "is_active": self.is_active, "is_running": task_running,
            "config_params": self.config_params, "current_position_size": self.current_position_size,
            "realized_pnl": self.realized_pnl, "total_trades": self.total_trades,
        }

    # --- Bot Actions ---
    
    async def _place_order(self, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Optional[Dict]:
        """Places an order via Binance client and records it."""
        client = await get_binance_client()
        if not client:
            self.logger.error("Cannot place order: Binance client not available.")
            return None
            
        side_upper = side.upper()
        type_upper = order_type.upper()
        log_price = f" @ {price}" if price else " @ Market"
        self.logger.info(f"Attempting to place {side_upper} {type_upper} order for {quantity:.8f} {self.symbol}{log_price}")
        
        loop = asyncio.get_event_loop()
        order_params = {} 
        try:
            # Prepare parameters carefully
            order_params = { 
                'symbol': self.symbol, 
                'side': side_upper, # Ensure side is uppercase
                'type': type_upper # Ensure type is uppercase
            }
            
            if type_upper == 'MARKET' and side_upper == 'BUY':
                 quote_qty = getattr(self, 'purchase_amount_quote', 0) 
                 if quote_qty > 0:
                     order_params['quoteOrderQty'] = quote_qty
                     self.logger.debug(f"Using quoteOrderQty: {quote_qty}")
                 elif quantity > 0: # Fallback to base quantity if quote not set/applicable
                      order_params['quantity'] = quantity 
                 else:
                      raise ValueError("Market BUY order requires positive 'quantity' or 'purchase_amount_quote'.")
            elif quantity > 0: # Base quantity for LIMIT or MARKET SELL
                 order_params['quantity'] = quantity
            else:
                 # Allow quantity=0 for DCA quoteOrderQty case, raise otherwise
                 if not (type_upper == 'MARKET' and side_upper == 'BUY' and getattr(self, 'purchase_amount_quote', 0) > 0):
                      raise ValueError("Order requires positive 'quantity'.")

            if type_upper == 'LIMIT':
                if price is None or price <= 0: raise ValueError("Price must be positive for LIMIT orders.")
                # TODO: Fetch symbol precision rules from exchange info for price/qty formatting
                order_params['price'] = str(price) 
                order_params['timeInForce'] = 'GTC' 
            
            self.logger.debug(f"Executing client.create_order with params: {order_params}")
            order = await loop.run_in_executor(None, client.create_order, **order_params)
            self.logger.info(f"Binance API response for create_order: {order}") 
            
            # --- Update Bot State & Record Trade ---
            if order and order.get('orderId'): 
                executed_qty = float(order.get('executedQty', 0))
                
                if executed_qty > 0:
                    self.total_trades += 1
                    # Simplistic state update - needs refinement for avg price etc.
                    avg_fill_price = self._parse_order_to_trade_details(order, side_upper, type_upper)['price'] or 0
                    if side_upper == 'BUY':
                        # TODO: Update average entry price correctly
                        new_total_cost = (self.entry_price * self.current_position_size if self.entry_price else 0) + (avg_fill_price * executed_qty)
                        self.current_position_size += executed_qty
                        self.entry_price = new_total_cost / self.current_position_size if self.current_position_size > 0 else None
                    elif side_upper == 'SELL':
                         # TODO: Calculate realized PnL correctly
                         if self.entry_price:
                              self.realized_pnl += (avg_fill_price - self.entry_price) * executed_qty
                         self.current_position_size -= executed_qty
                         if self.current_position_size < 1e-9: 
                              self.current_position_size = 0.0
                              self.entry_price = None 

                # Record in DB
                trade_details = self._parse_order_to_trade_details(order, side_upper, type_upper)
                if trade_details["quantity"] > 0:
                    # Use run_in_executor if record_trade becomes complex/blocking
                    await record_trade(
                        bot_config_id=self.bot_id,
                        user_id=uuid.UUID(self.user_id), 
                        trade_data=trade_details
                    )
                else:
                     self.logger.warning(f"Order {order.get('orderId')} has zero executed quantity. Not recording trade.")
            else:
                 self.logger.warning(f"Order placement might have failed or response format unexpected: {order}")

            return order 
        except (BinanceAPIException, BinanceOrderException) as e:
             # Log specific Binance errors
             self.logger.error(f"Binance API/Order Error placing order: {e} (Code: {e.code}, Message: {e.message}) Params: {order_params}", exc_info=True)
             return None
        except ValueError as e: # Catch specific validation errors
             self.logger.error(f"Value error preparing order: {e} Params: {order_params}", exc_info=True)
             return None
        except Exception as e:
            self.logger.error(f"Unexpected error placing order: {e} Params: {order_params}", exc_info=True)
            return None

    def _parse_order_to_trade_details(self, order: Dict, side: str, order_type: str) -> Dict:
        """Helper to extract trade details from a Binance order response."""
        timestamp_ms = order.get('transactTime', datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        timestamp_iso = datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc).isoformat()
        executed_qty = float(order.get('executedQty', 0))
        order_price_str = order.get('price', '0') 
        order_price = float(order_price_str) if order_price_str and float(order_price_str) > 0 else None
        
        commission = 0.0
        commission_asset = None
        avg_fill_price = order_price 

        if order.get('fills'):
            fills = order.get('fills', [])
            if fills:
                 commission = sum(float(fill.get('commission', 0)) for fill in fills)
                 commission_asset = fills[0].get('commissionAsset')
                 total_cost = sum(float(f.get('price', 0)) * float(f.get('qty', 0)) for f in fills)
                 total_qty = sum(float(f.get('qty', 0)) for f in fills)
                 if total_qty > 0: avg_fill_price = total_cost / total_qty
                 else: avg_fill_price = None 
        
        final_price = avg_fill_price if avg_fill_price is not None else order_price

        return {
            "binance_order_id": str(order.get('orderId')), "symbol": order.get('symbol', self.symbol),
            "side": order.get('side', side), "type": order.get('type', order_type),
            "price": final_price, "quantity": executed_qty,
            "commission": commission, "commission_asset": commission_asset,
            "timestamp": timestamp_iso
        }

    async def _get_account_balance(self, asset: str) -> Optional[Dict]:
        client = await get_binance_client()
        if not client: self.logger.error("Cannot get balance: Binance client not available."); return None
        loop = asyncio.get_event_loop()
        try:
            balance_data = await loop.run_in_executor(None, lambda: client.get_asset_balance(asset=asset))
            if balance_data:
                 self.logger.debug(f"Fetched balance for {asset}: {balance_data}")
                 return {
                     "asset": balance_data.get('asset'),
                     "free": float(balance_data.get('free', 0)), 
                     "locked": float(balance_data.get('locked', 0)) 
                 }
            else:
                 self.logger.warning(f"No balance data returned for asset {asset}.")
                 return {"asset": asset, "free": 0.0, "locked": 0.0} 
        except Exception as e:
            self.logger.error(f"Failed to get account balance for {asset}: {e}", exc_info=True)
            return None

    async def _update_and_record_performance(self):
        self.logger.debug("Triggered placeholder performance update.") 
        try:
            current_price = await get_current_price(self.symbol)
            unrealized_pnl = 0.0
            if self.current_position_size > 0 and self.entry_price and current_price:
                 unrealized_pnl = (current_price - self.entry_price) * self.current_position_size
            
            quote_asset = self.symbol[-4:] if self.symbol.endswith('USDT') else self.symbol[-3:] 
            base_asset = self.symbol[:-len(quote_asset)]
            quote_balance_data = await self._get_account_balance(quote_asset)
            base_balance_data = await self._get_account_balance(base_asset)
            cash_balance = quote_balance_data['free'] if quote_balance_data else 0.0
            base_asset_value = (base_balance_data['free'] + base_balance_data['locked']) * current_price if base_balance_data and current_price else 0.0
            portfolio_value = cash_balance + base_asset_value 
            win_rate = 50.0 # Dummy
            
            performance_data = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_pnl": self.realized_pnl + unrealized_pnl, 
                "total_trades": self.total_trades, "win_rate": win_rate, 
                "portfolio_value": portfolio_value, 
                "metrics": { "unrealized_pnl": unrealized_pnl, "realized_pnl": self.realized_pnl }
            }
            await record_performance_snapshot(
                bot_config_id=self.bot_id, user_id=uuid.UUID(self.user_id),
                performance_data=performance_data
            )
        except Exception as e:
             self.logger.error(f"Error during performance update/record: {e}", exc_info=True)
