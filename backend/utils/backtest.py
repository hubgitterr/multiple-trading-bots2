import pandas as pd
import logging
from typing import Dict, Any, Optional, List
import uuid
import random # For dummy results

# Import utility functions
from .indicators import calculate_rsi, calculate_macd # etc.
from .binance_client import get_historical_klines_df # To fetch data
from .grid import calculate_grid_levels # For grid bot logic

logger = logging.getLogger(__name__)

# --- Backtesting Configuration ---
INITIAL_CAPITAL = 10000.0 # Example starting capital in quote currency
COMMISSION_RATE = 0.001 # Example trading commission (0.1%)

# --- Backtesting Result Structure ---
# TODO: Define a more structured result class or TypedDict
BacktestResult = Dict[str, Any] 

# --- Helper Function for Grid Backtest ---
# Define it outside run_backtest so it's accessible within the grid logic block
def _find_next_grid_level(current_level: float, direction: str, grid_levels: List[float]) -> Optional[float]:
    """Finds the next grid level above ('up') or below ('down') the current level."""
    try:
        # Ensure levels are sorted (should be from calculate_grid_levels)
        sorted_levels = sorted(grid_levels) 
        current_index = sorted_levels.index(current_level)
        if direction == 'up' and current_index < len(sorted_levels) - 1:
            return sorted_levels[current_index + 1]
        elif direction == 'down' and current_index > 0:
            return sorted_levels[current_index - 1]
        else:
            return None 
    except ValueError:
        logger.warning(f"Level {current_level} not found in calculated grid levels: {grid_levels}")
        return None
    except IndexError:
         logger.warning(f"Index out of bounds while finding next grid level for {current_level}.")
         return None

async def run_backtest(
    bot_config: Dict[str, Any], 
    start_date: str, 
    end_date: str
) -> Optional[BacktestResult]:
    """
    Runs a backtest for a given bot configuration over a historical period.
    """
    bot_type = bot_config.get('bot_type')
    symbol = bot_config.get('symbol')
    config_params = bot_config.get('config_params', {})
    
    if not bot_type or not symbol:
        logger.error("Backtest requires bot_type and symbol in configuration.")
        return None

    logger.info(f"Starting backtest for {bot_type} bot on {symbol} from {start_date} to {end_date}")

    # 1. Fetch Historical Data
    interval = config_params.get('candle_interval', '1h') # Default interval
    if bot_type == 'grid':
         interval = config_params.get('candle_interval', '15m') # Grid might use smaller interval
         
    try:
        historical_data = await get_historical_klines_df(symbol, interval, start_date, end_date)
        if historical_data is None or historical_data.empty:
            logger.error(f"Failed to fetch or process historical data for {symbol}.")
            return None
        logger.info(f"Fetched {len(historical_data)} data points for backtest.")
    except Exception as e:
         logger.error(f"Error fetching historical data during backtest setup: {e}", exc_info=True)
         return None

    # 2. Simulate Strategy Logic based on bot_type
    
    # --- Initialize Portfolio ---
    cash = INITIAL_CAPITAL
    position_size = 0.0 # Amount of base asset held
    equity = [INITIAL_CAPITAL] # Start equity curve
    trades_log: List[Dict[str, Any]] = []
    
    # --- Run Simulation based on Bot Type ---
    if bot_type == 'momentum':
        logger.info("Running Momentum backtest simulation...")
        last_signal = None 
        rsi_period = int(config_params.get('rsi_period', 14))
        rsi_oversold = float(config_params.get('rsi_oversold', 30))
        rsi_overbought = float(config_params.get('rsi_overbought', 70))
        macd_fast = int(config_params.get('macd_fast', 12))
        macd_slow = int(config_params.get('macd_slow', 26))
        macd_signal = int(config_params.get('macd_signal', 9))
        trade_quantity_base = float(config_params.get('trade_quantity', 0)) 

        if trade_quantity_base <= 0:
             logger.error("Trade quantity must be positive for Momentum backtest.")
             return None 

        try:
            historical_data['rsi'] = calculate_rsi(historical_data['close'], rsi_period)
            macd_df = calculate_macd(historical_data['close'], macd_fast, macd_slow, macd_signal)
            historical_data = pd.concat([historical_data, macd_df], axis=1)
            first_valid_index = max(rsi_period, macd_slow + macd_signal) 
            historical_data = historical_data.iloc[first_valid_index:]
            if historical_data.empty: raise ValueError("Not enough data after indicator calculation.")
        except Exception as e:
            logger.error(f"Error calculating indicators for Momentum backtest: {e}", exc_info=True)
            return None

        for i in range(len(historical_data)):
            current_time = historical_data.index[i]
            current_price = historical_data['close'].iloc[i]
            current_rsi = historical_data['rsi'].iloc[i]
            current_macd = historical_data['MACD'].iloc[i]
            current_signal = historical_data['Signal'].iloc[i]
            
            current_value = cash + (position_size * current_price)
            if i > 0: equity.append(current_value) 

            buy_signal = current_rsi > rsi_oversold and current_macd > current_signal
            sell_signal = current_rsi < rsi_overbought or current_macd < current_signal

            if buy_signal and position_size == 0 and last_signal != 'BUY': 
                cost = current_price * trade_quantity_base * (1 + COMMISSION_RATE)
                if cash >= cost:
                    cash -= cost; position_size += trade_quantity_base; last_signal = 'BUY'
                    trades_log.append({"timestamp": current_time.isoformat(), "side": "BUY", "price": current_price, "quantity": trade_quantity_base})
            elif sell_signal and position_size > 0 and last_signal != 'SELL': 
                proceeds = current_price * position_size * (1 - COMMISSION_RATE)
                cash += proceeds; sold_quantity = position_size; position_size = 0.0; last_signal = 'SELL'
                trades_log.append({"timestamp": current_time.isoformat(), "side": "SELL", "price": current_price, "quantity": sold_quantity})
                
    elif bot_type == 'grid':
         logger.info("Running Grid backtest simulation (simplified)...")
         lower_bound = float(config_params.get('lower_bound', 0))
         upper_bound = float(config_params.get('upper_bound', 0))
         num_grids = int(config_params.get('num_grids', 5))
         grid_mode = config_params.get('grid_mode', 'arithmetic')
         investment_amount = float(config_params.get('investment_amount', 0))

         if not (lower_bound > 0 and upper_bound > lower_bound and num_grids >= 2 and investment_amount > 0):
             logger.error("Invalid parameters for Grid backtest.")
             return None
             
         grid_levels = calculate_grid_levels(lower_bound, upper_bound, num_grids, grid_mode)
         
         initial_price = historical_data['open'].iloc[0]
         buy_levels_below = [level for level in grid_levels if level < initial_price]
         
         if not buy_levels_below:
              pending_buy_orders = {}
         else:
             value_per_order = investment_amount / len(buy_levels_below)
             pending_buy_orders = {level: value_per_order / level for level in buy_levels_below} 
             
         logger.info(f"Initial pending buy orders: {len(pending_buy_orders)}")
         # TODO: Simulate initial sell orders 
         pending_sell_orders = {} # Placeholder for sells placed after buys fill

         for i in range(len(historical_data)):
             current_time = historical_data.index[i]
             low_price = historical_data['low'].iloc[i]
             high_price = historical_data['high'].iloc[i] # Needed for sell fills
             close_price = historical_data['close'].iloc[i] 

             current_value = cash + (position_size * close_price)
             if i > 0: equity.append(current_value)

             # Check for buy fills 
             filled_buys = []
             for level, quantity in pending_buy_orders.items():
                 if low_price <= level:
                     cost = level * quantity * (1 + COMMISSION_RATE)
                     if cash >= cost:
                         cash -= cost; position_size += quantity
                         trades_log.append({"timestamp": current_time.isoformat(), "side": "BUY", "price": level, "quantity": quantity})
                         filled_buys.append(level)
                         
                         # Simulate placing corresponding sell order
                         sell_level = _find_next_grid_level(level, 'up', grid_levels) 
                         if sell_level:
                              pending_sell_orders[sell_level] = quantity # Track pending sell
                              logger.debug(f"Simulating placement of SELL @ {sell_level:.2f} for filled BUY @ {level:.2f}")
                         else:
                              logger.warning(f"Grid BUY filled @ {level:.2f}, but no higher level to place SELL.")
                              
             for level in filled_buys: pending_buy_orders.pop(level, None)
                 
             # Check for sell fills (from orders placed after buys)
             filled_sells = []
             for level, quantity in pending_sell_orders.items():
                  if high_price >= level:
                       proceeds = level * quantity * (1 - COMMISSION_RATE)
                       # Ensure we have enough position to sell (can happen with partial fills in reality)
                       if position_size >= quantity: 
                            cash += proceeds; position_size -= quantity
                            trades_log.append({"timestamp": current_time.isoformat(), "side": "SELL", "price": level, "quantity": quantity})
                            filled_sells.append(level)
                            logger.debug(f"{current_time} - Grid SELL filled @ {level:.2f}, Qty: {quantity:.4f}, Cash: {cash:.2f}")
                            
                            # Simulate placing corresponding buy order
                            buy_level = _find_next_grid_level(level, 'down', grid_levels)
                            if buy_level:
                                 pending_buy_orders[buy_level] = quantity # Track pending buy
                                 logger.debug(f"Simulating placement of BUY @ {buy_level:.2f} for filled SELL @ {level:.2f}")
                            else:
                                 logger.warning(f"Grid SELL filled @ {level:.2f}, but no lower level to place BUY.")
                       else:
                            logger.warning(f"Sell signal @ {level} but insufficient position ({position_size} < {quantity})")


             for level in filled_sells: pending_sell_orders.pop(level, None)

    elif bot_type == 'dca':
         logger.info("Running DCA backtest simulation...")
         purchase_amount_quote = float(config_params.get('purchase_amount_quote', 0))
         purchase_interval_seconds = int(config_params.get('purchase_interval_seconds', 86400))
         last_purchase_timestamp = None

         if purchase_amount_quote <= 0 or purchase_interval_seconds <= 0:
              logger.error("Invalid parameters for DCA backtest.")
              return None

         for i in range(len(historical_data)):
             current_time = historical_data.index[i]
             current_price = historical_data['close'].iloc[i]
             
             current_value = cash + (position_size * current_price)
             if i > 0: equity.append(current_value)

             make_purchase = False
             if last_purchase_timestamp is None: 
                 make_purchase = True
             else:
                 if isinstance(last_purchase_timestamp, pd.Timestamp):
                      time_since_last = (current_time - last_purchase_timestamp).total_seconds()
                      if time_since_last >= purchase_interval_seconds: make_purchase = True
                 else: 
                      logger.error("last_purchase_timestamp is not valid."); make_purchase = True 
             
             if make_purchase:
                 quantity_to_buy = purchase_amount_quote / current_price 
                 cost = purchase_amount_quote * (1 + COMMISSION_RATE) 
                 if cash >= cost:
                     cash -= cost; position_size += quantity_to_buy
                     last_purchase_timestamp = current_time
                     trades_log.append({"timestamp": current_time.isoformat(), "side": "BUY", "price": current_price, "quantity": quantity_to_buy})

    else:
        logger.error(f"Unsupported bot_type '{bot_type}' for backtesting.")
        return None

    # --- Final Calculations & Result Formatting ---
    if not equity: 
         logger.warning("Equity curve is empty.")
         return None 
         
    final_portfolio_value = equity[-1]
    total_pnl = final_portfolio_value - INITIAL_CAPITAL
    total_pnl_percent = (total_pnl / INITIAL_CAPITAL) * 100 if INITIAL_CAPITAL else 0
    total_trades = len(trades_log)
    
    wins = sum(1 for i in range(1, len(trades_log)) if trades_log[i]['side'] == 'SELL' and trades_log[i-1]['side'] == 'BUY' and trades_log[i]['price'] > trades_log[i-1]['price'])
    losses = sum(1 for i in range(1, len(trades_log)) if trades_log[i]['side'] == 'SELL' and trades_log[i-1]['side'] == 'BUY' and trades_log[i]['price'] <= trades_log[i-1]['price'])
    win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0.0

    max_drawdown = 0.0
    peak_equity = -float('inf') 
    equity_series = pd.Series(equity) 
    
    for value in equity_series:
        if value > peak_equity: peak_equity = value
        drawdown = (peak_equity - value) / peak_equity if peak_equity > 0 else 0
        if drawdown > max_drawdown: max_drawdown = drawdown
            
    sharpe_ratio = random.uniform(0.1, 1.0) # Placeholder
    
    equity_curve_timestamps = historical_data.index.strftime('%Y-%m-%dT%H:%M:%SZ').tolist()
    equity_curve_values = equity
    
    results: BacktestResult = {
        "start_date": start_date, "end_date": end_date, "symbol": symbol,
        "bot_type": bot_type, "config_params": config_params,
        "initial_capital": INITIAL_CAPITAL, "final_portfolio_value": final_portfolio_value,
        "total_pnl": total_pnl, "total_pnl_percent": total_pnl_percent,
        "total_trades": total_trades, "win_rate": win_rate,
        "metrics": { "sharpe_ratio": sharpe_ratio, "max_drawdown": max_drawdown * 100 },
        "equity_curve": { "timestamps": equity_curve_timestamps, "values": equity_curve_values },
        "trades": trades_log 
    }
    
    logger.info(f"Backtest completed for {symbol}. Final PnL: {total_pnl:.2f}")
    return results

# --- Example Usage ---
# async def main():
#     test_config = {
#         'bot_type': 'grid', 
#         'symbol': 'BTCUSDT', 
#         'config_params': { 
#             'lower_bound': 70000, 'upper_bound': 90000, 'num_grids': 10, 
#             'investment_amount': 5000, 'candle_interval': '1h' 
#         }
#     }
#     results = await run_backtest(test_config, "1 Feb, 2024", "28 Feb, 2024")
#     if results:
#         print(f"Backtest PnL: {results['total_pnl']:.2f}")
#         print(f"Number of trades: {results['total_trades']}")
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())
