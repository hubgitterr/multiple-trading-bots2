import asyncio
import logging
import pandas as pd
from typing import Dict, Any, Optional # Import Optional
import datetime

from .base_bot import BaseTradingBot
from ..utils.binance_client import get_historical_klines # Corrected import
from ..utils.indicators import calculate_rsi, calculate_macd, calculate_sma # Import necessary indicators

class MomentumTradingBot(BaseTradingBot):
    """
    Implements a momentum trading strategy with an optional stop-loss.
    Example Strategy: Buy when RSI crosses above a threshold and MACD is bullish, 
                      Sell when RSI crosses below another threshold, MACD turns bearish, or stop-loss is hit.
    """
    def __init__(self, bot_config: Dict[str, Any], user_id: str):
        super().__init__(bot_config, user_id)
        self.bot_type = "momentum" # Explicitly set bot type
        self.logger = logging.getLogger(f"{self.bot_type}.{self.name}.{self.bot_id}")
        
        # --- Strategy Specific Parameters ---
        self.rsi_period: int = int(self.config_params.get('rsi_period', 14))
        self.rsi_oversold: float = float(self.config_params.get('rsi_oversold', 30))
        self.rsi_overbought: float = float(self.config_params.get('rsi_overbought', 70))
        self.macd_fast: int = int(self.config_params.get('macd_fast', 12))
        self.macd_slow: int = int(self.config_params.get('macd_slow', 26))
        self.macd_signal: int = int(self.config_params.get('macd_signal', 9))
        self.candle_interval: str = self.config_params.get('candle_interval', '1h') 
        self.lookback_periods: int = int(self.config_params.get('lookback_periods', 100)) 
        self.trade_quantity: float = float(self.config_params.get('trade_quantity', 0)) # Base asset quantity
        self.stop_loss_percent: Optional[float] = float(self.config_params.get('stop_loss_percent', 0)) # e.g., 0.02 for 2%
        
        # --- State Variables ---
        self.in_position: bool = False 
        self.current_entry_price: Optional[float] = None # Track entry price for stop-loss calc
        self.stop_loss_price: Optional[float] = None # Calculated stop-loss level
        
        if self.trade_quantity <= 0:
             raise ValueError("Trade quantity must be positive.")

        log_params = f"RSI({self.rsi_period},{self.rsi_oversold}/{self.rsi_overbought}), MACD({self.macd_fast},{self.macd_slow},{self.macd_signal}), Interval({self.candle_interval}), Qty({self.trade_quantity})"
        if self.stop_loss_percent and self.stop_loss_percent > 0:
            log_params += f", StopLoss({self.stop_loss_percent*100}%)"
        else:
             self.stop_loss_percent = None # Ensure it's None if 0 or not provided

        self.logger.info(f"Momentum Bot '{self.name}' initialized with params: {log_params}")

    def _get_interval_seconds(self) -> int:
        """Helper to convert interval string to seconds for sleep."""
        # TODO: Make this more robust using a library or regex
        try:
            if 'm' in self.candle_interval:
                return int(self.candle_interval.replace('m', '')) * 60
            elif 'h' in self.candle_interval:
                return int(self.candle_interval.replace('h', '')) * 3600
            elif 'd' in self.candle_interval:
                return int(self.candle_interval.replace('d', '')) * 86400
            elif 'w' in self.candle_interval:
                 return int(self.candle_interval.replace('w', '')) * 604800
            else: # Assume minutes if no unit? Or raise error?
                 return int(self.candle_interval) * 60 
        except ValueError:
             self.logger.warning(f"Could not parse candle interval '{self.candle_interval}'. Defaulting to 1 hour.")
             return 3600

    async def _run_logic(self):
        """Core logic loop for the momentum bot."""
        self.logger.info(f"Starting momentum logic loop for {self.symbol}...")
        
        interval_seconds = self._get_interval_seconds()
        
        while self.is_active:
            try:
                self.logger.debug(f"Running check for {self.symbol} at {datetime.datetime.utcnow()} UTC")
                
                # 1. Fetch Historical Data
                required_candles = max(self.lookback_periods, self.macd_slow + self.macd_signal) + 5 
                # Use a more reliable way to get start time string if possible
                # Example: Calculate timestamp and format, or use relative like "X hours ago UTC"
                # For simplicity, keeping the minute-based calculation for now
                minutes_ago = required_candles * interval_seconds // 60
                start_time_str = f"{minutes_ago} minutes ago UTC" 
                
                klines = await get_historical_klines(self.symbol, self.candle_interval, start_str=start_time_str)
                
                if not klines or len(klines) < required_candles:
                    self.logger.warning(f"Insufficient kline data ({len(klines) if klines else 0} candles < {required_candles}). Skipping check.")
                    await asyncio.sleep(interval_seconds) 
                    continue

                # 2. Prepare DataFrame
                df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                df['close'] = df['close'].astype(float)
                df['low'] = df['low'].astype(float) # Need low price for stop-loss check
                
                # 3. Calculate Indicators
                df['rsi'] = calculate_rsi(df['close'], self.rsi_period)
                macd_df = calculate_macd(df['close'], self.macd_fast, self.macd_slow, self.macd_signal)
                df = pd.concat([df, macd_df], axis=1)
                
                # Drop NaNs after indicator calculation
                df.dropna(inplace=True)
                if df.empty:
                     self.logger.warning("DataFrame empty after calculating indicators and dropping NaNs. Skipping check.")
                     await asyncio.sleep(interval_seconds)
                     continue

                # Get the latest complete candle's data
                latest = df.iloc[-1] # Use last row now that NaNs are dropped
                
                self.logger.debug(f"Latest data for {self.symbol}: Close={latest['close']:.4f}, RSI={latest['rsi']:.2f}, MACD={latest['MACD']:.4f}, Signal={latest['Signal']:.4f}")

                # 4. Apply Trading Logic & State Management
                
                # --- Stop Loss Check (only if in position) ---
                if self.in_position and self.stop_loss_price and latest['low'] <= self.stop_loss_price:
                     self.logger.info(f"STOP LOSS triggered for {self.symbol} at low price {latest['low']:.4f} (Stop @ {self.stop_loss_price:.4f})")
                     # Use current position size for selling
                     sell_quantity = self.current_position_size 
                     if sell_quantity > 0:
                         order_result = await self._place_order(side='SELL', order_type='MARKET', quantity=sell_quantity) 
                         if order_result and order_result.get('status') == 'FILLED':
                             self.logger.info(f"Exited LONG position for {self.symbol} due to STOP LOSS.")
                             # Reset state AFTER successful exit
                             self.in_position = False
                             self.current_entry_price = None
                             self.stop_loss_price = None
                         else:
                             self.logger.error(f"Failed to place SELL order for {self.symbol} (STOP LOSS). Position might still be open.")
                             # TODO: Add retry logic or alert mechanism for failed stop-loss orders
                     else:
                          self.logger.warning("Stop loss triggered but position size is zero or negative. Resetting state.")
                          self.in_position = False
                          self.current_entry_price = None
                          self.stop_loss_price = None

                # --- Entry Signal Check (only if not in position) ---
                elif not self.in_position:
                    buy_signal = latest['rsi'] > self.rsi_oversold and latest['MACD'] > latest['Signal']
                    if buy_signal:
                         self.logger.info(f"BUY SIGNAL for {self.symbol}: RSI ({latest['rsi']:.2f}) > {self.rsi_oversold} and MACD bullish.")
                         order_result = await self._place_order(side='BUY', order_type='MARKET', quantity=self.trade_quantity)
                         if order_result and order_result.get('status') == 'FILLED':
                             self.in_position = True
                             # Use actual fill price if available, else candle close
                             entry_price_approx = self._parse_order_to_trade_details(order_result, 'BUY', 'MARKET')['price'] or latest['close']
                             self.current_entry_price = entry_price_approx
                             # Set stop loss price if configured
                             if self.stop_loss_percent:
                                 self.stop_loss_price = self.current_entry_price * (1 - self.stop_loss_percent)
                                 self.logger.info(f"Entered LONG position for {self.symbol} @ ~{self.current_entry_price:.4f}. Stop loss set to {self.stop_loss_price:.4f}")
                             else:
                                 self.logger.info(f"Entered LONG position for {self.symbol} @ ~{self.current_entry_price:.4f}. No stop loss.")
                         else:
                             self.logger.error(f"Failed to place or confirm BUY order for {self.symbol}.")
                             
                # --- Regular Exit Signal Check (only if in position and stop loss wasn't hit) ---
                elif self.in_position: 
                    sell_signal = latest['rsi'] < self.rsi_overbought or latest['MACD'] < latest['Signal']
                    if sell_signal:
                        self.logger.info(f"SELL SIGNAL for {self.symbol}: RSI ({latest['rsi']:.2f}) < {self.rsi_overbought} or MACD bearish.")
                        sell_quantity = self.current_position_size # Sell the entire position
                        if sell_quantity > 0:
                            order_result = await self._place_order(side='SELL', order_type='MARKET', quantity=sell_quantity)
                            if order_result and order_result.get('status') == 'FILLED':
                                self.logger.info(f"Exited LONG position for {self.symbol} based on signal.")
                                # Reset state
                                self.in_position = False
                                self.current_entry_price = None
                                self.stop_loss_price = None
                            else:
                                 self.logger.error(f"Failed to place SELL order for {self.symbol} based on signal.")
                        else:
                             self.logger.warning("Sell signal triggered but position size is zero or negative. Resetting state.")
                             self.in_position = False
                             self.current_entry_price = None
                             self.stop_loss_price = None


                # 5. Wait for the next interval
                self.logger.debug(f"Check complete for {self.symbol}. Sleeping for {interval_seconds} seconds.")
                await asyncio.sleep(interval_seconds) 

            except asyncio.CancelledError:
                self.logger.info(f"Momentum logic loop for {self.symbol} cancelled.")
                break 
            except Exception as e:
                self.logger.error(f"Error in momentum logic loop for {self.symbol}: {e}", exc_info=True)
                await asyncio.sleep(60) 

        self.logger.info(f"Momentum logic loop for {self.symbol} stopped.")
        # Reset state upon stopping
        self.in_position = False
        self.current_entry_price = None
        self.stop_loss_price = None
