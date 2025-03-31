import asyncio
import logging
from typing import Dict, Any, Optional # Import Optional
import datetime

from .base_bot import BaseTradingBot
# Import necessary client functions if needed (e.g., placing orders)

class DCATradingBot(BaseTradingBot):
    """
    Implements a Dollar-Cost Averaging (DCA) trading strategy.
    Periodically buys a fixed amount of quote currency worth of the base asset.
    """
    def __init__(self, bot_config: Dict[str, Any], user_id: str):
        super().__init__(bot_config, user_id)
        self.bot_type = "dca" # Explicitly set bot type
        self.logger = logging.getLogger(f"{self.bot_type}.{self.name}.{self.bot_id}")

        # --- Strategy Specific Parameters ---
        self.purchase_amount_quote: float = float(self.config_params.get('purchase_amount_quote', 0)) 
        self.purchase_interval_seconds: int = int(self.config_params.get('purchase_interval_seconds', 86400)) 
        # TODO: Add parameters for dip buying, trailing stop loss if needed later

        # --- State Variables ---
        self.last_purchase_time: Optional[datetime.datetime] = None

        if self.purchase_amount_quote <= 0:
            raise ValueError("DCA purchase amount (quote currency) must be positive.")
        if self.purchase_interval_seconds <= 0:
             raise ValueError("DCA purchase interval must be positive.")

        self.logger.info(f"DCA Bot '{self.name}' initialized: Amount({self.purchase_amount_quote} quote), Interval({self.purchase_interval_seconds}s)")

    async def _run_logic(self):
        """Core logic loop for the DCA bot."""
        self.logger.info(f"Starting DCA logic loop for {self.symbol}...")
        
        while self.is_active:
            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                
                # Check if it's time for the next purchase
                make_purchase = False
                time_to_wait = self.purchase_interval_seconds # Default wait time
                
                if self.last_purchase_time is None:
                    make_purchase = True
                    self.logger.info(f"First run for DCA bot {self.name}. Making initial purchase.")
                else:
                    time_since_last = (now - self.last_purchase_time).total_seconds()
                    if time_since_last >= self.purchase_interval_seconds:
                        make_purchase = True
                        self.logger.info(f"Interval of {self.purchase_interval_seconds}s passed. Time for DCA purchase for {self.name}.")
                    else:
                         time_to_wait = self.purchase_interval_seconds - time_since_last
                         self.logger.debug(f"Next DCA purchase for {self.name} in {time_to_wait:.0f} seconds.")

                if make_purchase:
                    self.logger.info(f"Attempting DCA purchase for {self.symbol}: spending {self.purchase_amount_quote} quote currency.")
                    
                    # Use the base class method which handles DB recording
                    # Pass quantity=0 because we are using quoteOrderQty
                    order_result = await self._place_order(
                        side='BUY', 
                        order_type='MARKET', 
                        quantity=0 
                    )
                            
                    if order_result and order_result.get('status') == 'FILLED':
                        self.logger.info(f"DCA Market BUY order placed successfully: {order_result.get('orderId')}")
                        self.last_purchase_time = now # Update last purchase time only on success
                    else:
                        self.logger.error(f"Failed to place or confirm DCA market BUY order for {self.symbol}.")
                        # Don't update last_purchase_time if order failed
                        time_to_wait = 60 # Wait 1 minute before checking again after failure

                # Wait until the next purchase time, checking for stop signal periodically
                self.logger.debug(f"DCA check complete for {self.name}. Waiting for {time_to_wait:.0f} seconds...")
                sleep_interval = 5 # Check every 5 seconds
                remaining_sleep = time_to_wait
                while remaining_sleep > 0 and self.is_active:
                     await asyncio.sleep(min(sleep_interval, remaining_sleep))
                     remaining_sleep -= sleep_interval
                
                # If loop exited because is_active became false, break outer loop
                if not self.is_active: break

            except asyncio.CancelledError:
                self.logger.info(f"DCA logic loop for {self.symbol} cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in DCA logic loop for {self.symbol}: {e}", exc_info=True)
                # Removed sleep(60) - loop will retry or exit based on is_active on next iteration

        self.logger.info(f"DCA logic loop for {self.symbol} stopped.")
