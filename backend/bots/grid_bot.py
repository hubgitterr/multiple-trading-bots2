import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional
import uuid
import datetime # For recording trade timestamp

from .base_bot import BaseTradingBot
from ..utils.grid import calculate_grid_levels, calculate_order_quantities
from ..utils.binance_client import get_current_price, get_order_status, place_order # Import necessary functions

class GridTradingBot(BaseTradingBot):
    """
    Implements a grid trading strategy.
    Places buy orders below the current price and sell orders above.
    When a buy fills, it places a sell order one grid level above.
    When a sell fills, it places a buy order one grid level below.
    """
    def __init__(self, bot_config: Dict[str, Any], user_id: str):
        super().__init__(bot_config, user_id)
        self.bot_type = "grid" # Explicitly set bot type
        self.logger = logging.getLogger(f"{self.bot_type}.{self.name}.{self.bot_id}")

        # --- Strategy Specific Parameters ---
        self.lower_bound: float = float(self.config_params.get('lower_bound', 0))
        self.upper_bound: float = float(self.config_params.get('upper_bound', 0))
        self.num_grids: int = int(self.config_params.get('num_grids', 5))
        self.grid_mode: str = self.config_params.get('grid_mode', 'arithmetic') # 'arithmetic' or 'geometric'
        self.investment_amount: float = float(self.config_params.get('investment_amount', 0)) # Quote currency for buy grid
        # TODO: Add base_asset_amount parameter for initial sell grid setup

        # --- State Variables ---
        self.grid_levels: List[float] = []
        # Store active order details {orderId: {price, quantity, side}}
        self.active_orders: Dict[str, Dict[str, Any]] = {} 
        # Store order IDs currently being processed to avoid race conditions
        self._processing_orders: set[str] = set() 

        if self.lower_bound <= 0 or self.upper_bound <= 0 or self.lower_bound >= self.upper_bound:
            raise ValueError("Invalid grid bounds provided.")
        if self.num_grids < 2: # Need at least two levels for a grid
             raise ValueError("Number of grids must be at least 2.")
        if self.investment_amount <= 0:
             # TODO: Allow grid setup with only sell orders if base_asset_amount is provided
             raise ValueError("Investment amount must be positive to set up buy grid.")

        self.logger.info(f"Grid Bot '{self.name}' initialized: Bounds({self.lower_bound}-{self.upper_bound}), Grids({self.num_grids}, {self.grid_mode}), Invest({self.investment_amount})")

    def _find_next_grid_level(self, current_level: float, direction: str) -> Optional[float]:
        """Finds the next grid level above ('up') or below ('down') the current level."""
        try:
            current_index = self.grid_levels.index(current_level)
            if direction == 'up' and current_index < len(self.grid_levels) - 1:
                return self.grid_levels[current_index + 1]
            elif direction == 'down' and current_index > 0:
                return self.grid_levels[current_index - 1]
            else:
                return None # No next level in that direction
        except ValueError:
            self.logger.warning(f"Level {current_level} not found in calculated grid levels: {self.grid_levels}")
            return None
        except IndexError:
             self.logger.warning(f"Index out of bounds while finding next grid level for {current_level}.")
             return None

    async def _setup_initial_grid(self):
        """Calculates grid levels and places initial buy/sell limit orders."""
        self.logger.info(f"Setting up initial grid for {self.symbol}...")
        
        # Cancel any potentially lingering orders from previous runs (important for restarts)
        await self._cancel_all_active_orders(fetch_open_orders=True) 
        self.active_orders = {} # Reset tracked orders

        current_price = await get_current_price(self.symbol)
        if current_price is None:
            self.logger.error("Could not fetch current price. Cannot set up grid.")
            return False 

        try:
            self.grid_levels = calculate_grid_levels(
                self.lower_bound, self.upper_bound, self.num_grids, self.grid_mode
            )
            if not self.grid_levels: raise ValueError("Grid level calculation failed.")
            
            # Calculate initial buy orders (levels below current price)
            buy_orders_to_place = calculate_order_quantities(
                self.investment_amount, self.grid_levels, current_price, 'equal_value'
            )
            
            # TODO: Calculate initial sell orders (levels above current price) based on base_asset_amount
            sell_orders_to_place = [] 
            
            self.logger.info(f"Calculated {len(buy_orders_to_place)} buy orders and {len(sell_orders_to_place)} sell orders to place.")

            # --- Place Orders ---
            orders_placed_count = 0
            # Place buy orders
            for level, quantity in buy_orders_to_place:
                # TODO: Add rounding based on symbol's precision rules
                self.logger.info(f"Placing BUY LIMIT order: {quantity:.8f} {self.symbol} @ {level:.4f}")
                # Use the base class method which now handles DB recording
                order_result = await self._place_order(side='BUY', order_type='LIMIT', quantity=quantity, price=level)
                if order_result and order_result.get('orderId'):
                    order_id = str(order_result['orderId'])
                    self.active_orders[order_id] = {'price': level, 'quantity': quantity, 'side': 'BUY'}
                    self.logger.info(f"BUY order placed successfully: ID {order_id}")
                    orders_placed_count += 1
                else:
                     self.logger.error(f"Failed to place BUY order at level {level}.")
                await asyncio.sleep(0.2) # Avoid hitting rate limits

            # TODO: Place sell orders similarly

            self.logger.info(f"Initial grid setup complete. {orders_placed_count} orders placed and tracked.")
            return True 

        except ValueError as e:
            self.logger.error(f"Error calculating grid: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during grid setup: {e}", exc_info=True)
            return False

    async def _check_and_handle_fills(self):
        """Checks status of active orders and places counter-orders for filled ones."""
        if not self.active_orders:
            return # Nothing to check

        # Create a copy of order IDs to check, as dict might change during iteration
        order_ids_to_check = list(self.active_orders.keys())
        
        for order_id in order_ids_to_check:
             # Skip if already processing or removed
            if order_id in self._processing_orders or order_id not in self.active_orders:
                continue

            try:
                self._processing_orders.add(order_id) # Mark as processing
                
                order_info = self.active_orders.get(order_id)
                if not order_info: continue # Should not happen if check above works

                self.logger.debug(f"Checking status for order {order_id} ({order_info['side']} @ {order_info['price']})")
                status_result = await get_order_status(self.symbol, order_id)

                if status_result and status_result.get('status') == 'FILLED':
                    self.logger.info(f"Order {order_id} ({order_info['side']} @ {order_info['price']}) FILLED!")
                    
                    filled_price = float(status_result.get('price', order_info['price'])) # Use actual fill price if available
                    filled_quantity = float(status_result.get('executedQty', order_info['quantity']))
                    
                    # Remove filled order from tracking
                    del self.active_orders[order_id] 
                    
                    # Place counter order
                    if order_info['side'] == 'BUY':
                        sell_level = self._find_next_grid_level(order_info['price'], 'up')
                        if sell_level:
                            self.logger.info(f"Placing counter SELL order for {filled_quantity:.8f} @ {sell_level:.4f}")
                            counter_order = await self._place_order(side='SELL', order_type='LIMIT', quantity=filled_quantity, price=sell_level)
                            if counter_order and counter_order.get('orderId'):
                                 new_order_id = str(counter_order['orderId'])
                                 self.active_orders[new_order_id] = {'price': sell_level, 'quantity': filled_quantity, 'side': 'SELL'}
                                 self.logger.info(f"Counter SELL order placed: ID {new_order_id}")
                            else:
                                 self.logger.error(f"Failed to place counter SELL order at {sell_level}")
                                 # TODO: Handle failure - retry? Alert?
                        else:
                             self.logger.warning(f"Buy filled at {order_info['price']}, but no higher grid level found to place sell order.")
                             
                    elif order_info['side'] == 'SELL':
                         buy_level = self._find_next_grid_level(order_info['price'], 'down')
                         if buy_level:
                             self.logger.info(f"Placing counter BUY order for {filled_quantity:.8f} @ {buy_level:.4f}")
                             counter_order = await self._place_order(side='BUY', order_type='LIMIT', quantity=filled_quantity, price=buy_level)
                             if counter_order and counter_order.get('orderId'):
                                 new_order_id = str(counter_order['orderId'])
                                 self.active_orders[new_order_id] = {'price': buy_level, 'quantity': filled_quantity, 'side': 'BUY'}
                                 self.logger.info(f"Counter BUY order placed: ID {new_order_id}")
                             else:
                                 self.logger.error(f"Failed to place counter BUY order at {buy_level}")
                                 # TODO: Handle failure
                         else:
                              self.logger.warning(f"Sell filled at {order_info['price']}, but no lower grid level found to place buy order.")

                elif status_result and status_result.get('status') in ['CANCELED', 'EXPIRED', 'REJECTED']:
                     self.logger.warning(f"Order {order_id} ({order_info['side']} @ {order_info['price']}) has status {status_result.get('status')}. Removing from active list.")
                     del self.active_orders[order_id]
                     # TODO: Potentially try to replace the order? Depends on strategy.
                
                elif not status_result:
                     # Error fetching status (logged in get_order_status), maybe temporary issue
                     self.logger.warning(f"Could not fetch status for order {order_id}. Will retry later.")
                     
                # else: Order is NEW, PARTIALLY_FILLED, PENDING_CANCEL - keep tracking

            except Exception as e:
                 self.logger.error(f"Error processing order {order_id}: {e}", exc_info=True)
            finally:
                 self._processing_orders.discard(order_id) # Ensure removal from processing set

            await asyncio.sleep(0.1) # Small delay between checking orders


    async def _run_logic(self):
        """Core logic loop for the grid bot."""
        self.logger.info(f"Starting grid logic loop for {self.symbol}...")
        
        setup_successful = await self._setup_initial_grid()
        
        if not setup_successful:
            self.logger.error("Grid setup failed. Stopping bot.")
            self.is_active = False 
            return

        while self.is_active:
            try:
                await self._check_and_handle_fills()
                
                # Wait before the next check cycle, checking for stop signal periodically
                sleep_duration = 30 # Check orders every 30 seconds (adjust as needed)
                sleep_interval = 5  # Check stop flag every 5 seconds
                remaining_sleep = sleep_duration
                while remaining_sleep > 0 and self.is_active:
                     await asyncio.sleep(min(sleep_interval, remaining_sleep))
                     remaining_sleep -= sleep_interval
                
                # If loop exited because is_active became false, break outer loop
                if not self.is_active: break

            except asyncio.CancelledError:
                self.logger.info(f"Grid logic loop for {self.symbol} cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in grid logic loop for {self.symbol}: {e}", exc_info=True)
                await asyncio.sleep(60) # Wait after error

        self.logger.info(f"Grid logic loop for {self.symbol} stopped.")
        await self._cancel_all_active_orders() # Cancel remaining orders on stop
        self.active_orders = {} 

    async def _cancel_all_active_orders(self, fetch_open_orders=False):
        """
        Cancels all currently tracked active orders or fetches and cancels all open orders for the symbol.
        
        Args:
            fetch_open_orders (bool): If True, fetches all open orders from the exchange 
                                      for this symbol and attempts to cancel them. 
                                      If False, only cancels orders tracked in self.active_orders.
        """
        client = await get_binance_client()
        if not client:
            self.logger.error("Cannot cancel orders: Binance client not available.")
            return

        orders_to_cancel_ids = set() # Use a set to avoid duplicates

        if fetch_open_orders:
            self.logger.info(f"Fetching all open orders for {self.symbol} to cancel...")
            loop = asyncio.get_event_loop()
            try:
                # Ensure get_open_orders is called correctly within executor
                open_orders = await loop.run_in_executor(None, lambda: client.get_open_orders(symbol=self.symbol))
                fetched_ids = {str(o['orderId']) for o in open_orders}
                orders_to_cancel_ids.update(fetched_ids)
                self.logger.info(f"Found {len(fetched_ids)} open orders on exchange.")
            except Exception as e:
                self.logger.error(f"Failed to fetch open orders for cancellation: {e}", exc_info=True)
                # Fallback to cancelling only locally tracked orders if fetch fails
                self.logger.warning("Falling back to cancelling only locally tracked orders.")
                orders_to_cancel_ids.update(self.active_orders.keys())
        else:
            orders_to_cancel_ids.update(self.active_orders.keys())


        if not orders_to_cancel_ids:
             self.logger.info("No orders found to cancel.")
             return

        self.logger.info(f"Attempting to cancel {len(orders_to_cancel_ids)} orders for bot {self.name}...")
        loop = asyncio.get_event_loop()
        cancelled_count = 0
        
        tasks = []
        for order_id in orders_to_cancel_ids:
             # Define async task for cancellation
             async def cancel_task(oid):
                 nonlocal cancelled_count
                 try:
                     self.logger.debug(f"Cancelling order {oid}...")
                     # Use run_in_executor for the synchronous cancel_order call
                     await loop.run_in_executor(None, lambda: client.cancel_order(symbol=self.symbol, orderId=oid))
                     self.logger.info(f"Cancelled order {oid}.")
                     cancelled_count += 1
                     return oid, True # Return ID and success
                 except BinanceAPIException as e_api:
                     if e_api.code == -2011: # Order filled/cancelled/expired
                         self.logger.warning(f"Order {oid} already closed or does not exist.")
                         return oid, True # Consider it 'successfully' handled
                     else:
                         self.logger.error(f"API Error cancelling order {oid}: {e_api}")
                         return oid, False # Return ID and failure
                 except Exception as e_exc:
                     self.logger.error(f"Unexpected error cancelling order {oid}: {e_exc}", exc_info=True)
                     return oid, False # Return ID and failure
                 finally:
                      # Always remove from local tracking after attempt
                      self.active_orders.pop(oid, None) 
                      self._processing_orders.discard(oid)

             tasks.append(cancel_task(order_id))

        # Run cancellation tasks concurrently
        results = await asyncio.gather(*tasks)
        
        successful_cancels = sum(1 for _, success in results if success)
        failed_cancels = len(results) - successful_cancels

        self.logger.info(f"Finished cancellation attempt. Successful: {successful_cancels}, Failed: {failed_cancels}.")
        # Clear local state again just in case
        self.active_orders = {}
        self._processing_orders = set()
