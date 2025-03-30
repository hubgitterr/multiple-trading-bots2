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
        # Amount of QUOTE currency to spend per purchase (e.g., 100 USDT)
        self.purchase_amount_quote: float = float(self.config_params.get('purchase_amount_quote', 0)) 
        # Frequency of purchases in seconds (e.g., 86400 for daily, 604800 for weekly)
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
                if self.last_purchase_time is None:
                    # First run after starting, make initial purchase
                    make_purchase = True
                    self.logger.info(f"First run for DCA bot {self.name}. Making initial purchase.")
                else:
                    time_since_last = (now - self.last_purchase_time).total_seconds()
                    if time_since_last >= self.purchase_interval_seconds:
                        make_purchase = True
                        self.logger.info(f"Interval of {self.purchase_interval_seconds}s passed. Time for DCA purchase for {self.name}.")
                    else:
                         # Calculate time until next purchase for logging/debugging
                         wait_time = self.purchase_interval_seconds - time_since_last
                         self.logger.debug(f"Next DCA purchase for {self.name} in {wait_time:.0f} seconds.")


                if make_purchase:
                    self.logger.info(f"Attempting DCA purchase for {self.symbol}: spending {self.purchase_amount_quote} quote currency.")
                    
                    # --- Place Market Buy Order ---
                    # For DCA, market orders are common to ensure execution.
                    # We need to specify the quoteOrderQty for market buys by quote amount.
                    
                    if not self._binance_client:
                         self.logger.error("Cannot place DCA order: Binance client not available.")
                         # Skip this cycle, will retry later
                    else:
                        loop = asyncio.get_event_loop()
                        try:
                            # Use create_order with quoteOrderQty for market buy by quote amount
                            order = await loop.run_in_executor(
                                None, 
                                self._binance_client.create_order, 
                                symbol=self.symbol, 
                                side='BUY', 
                                type='MARKET', 
                                quoteOrderQty=self.purchase_amount_quote
                            )
                            self.logger.info(f"DCA Market BUY order placed successfully: {order}")
                            self.last_purchase_time = now # Update last purchase time only on success
                            # TODO: Record trade in database
                            
                        except Exception as e:
                            self.logger.error(f"Failed to place DCA market BUY order for {self.symbol}: {e}", exc_info=True)
                            # Don't update last_purchase_time if order failed

                # Wait before the next check. Sleep for a fraction of the interval 
                # or a fixed short duration to ensure responsiveness to stop signals.
                # Sleeping for the full interval might delay stop requests.
                check_interval = min(60, self.purchase_interval_seconds // 10) # Check every minute or 1/10th of interval
                await asyncio.sleep(check_interval) 

            except asyncio.CancelledError:
                self.logger.info(f"DCA logic loop for {self.symbol} cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in DCA logic loop for {self.symbol}: {e}", exc_info=True)
                await asyncio.sleep(60) # Wait after error

        self.logger.info(f"DCA logic loop for {self.symbol} stopped.")
