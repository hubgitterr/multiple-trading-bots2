import pandas as pd
import numpy as np
import logging

# Configure logging
logger = logging.getLogger(__name__)

def calculate_sma(data: pd.Series, window: int) -> pd.Series:
    """Calculates the Simple Moving Average (SMA)."""
    if window <= 0:
        logger.error("SMA window must be positive.")
        raise ValueError("SMA window must be positive.")
    if len(data) < window:
        logger.warning(f"Data length ({len(data)}) is less than SMA window ({window}). Returning NaNs.")
        return pd.Series([np.nan] * len(data), index=data.index)
    return data.rolling(window=window, min_periods=window).mean()

def calculate_ema(data: pd.Series, window: int) -> pd.Series:
    """Calculates the Exponential Moving Average (EMA)."""
    if window <= 0:
        logger.error("EMA window must be positive.")
        raise ValueError("EMA window must be positive.")
    if len(data) < window:
         logger.warning(f"Data length ({len(data)}) is less than EMA window ({window}). Returning NaNs.")
         # EMA calculation needs sufficient data; returning NaNs might be safer than partial calculation
         return pd.Series([np.nan] * len(data), index=data.index)
    # Adjust=False matches common TA library behavior
    return data.ewm(span=window, adjust=False, min_periods=window).mean()

def calculate_rsi(data: pd.Series, window: int = 14) -> pd.Series:
    """Calculates the Relative Strength Index (RSI)."""
    if window <= 0:
        logger.error("RSI window must be positive.")
        raise ValueError("RSI window must be positive.")
    if len(data) < window + 1: # Need at least window+1 periods for delta calculation
        logger.warning(f"Data length ({len(data)}) insufficient for RSI window ({window}). Returning NaNs.")
        return pd.Series([np.nan] * len(data), index=data.index)

    delta = data.diff()
    
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Use EMA for average gain/loss calculation (common practice)
    avg_gain = calculate_ema(gain, window)
    avg_loss = calculate_ema(loss, window)
    
    # Handle division by zero if avg_loss is 0
    rs = np.where(avg_loss == 0, np.inf, avg_gain / avg_loss)
    
    rsi = 100 - (100 / (1 + rs))
    
    # Set initial NaNs where calculation wasn't possible
    rsi[:window] = np.nan 
    
    return rsi

def calculate_macd(data: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> pd.DataFrame:
    """
    Calculates the Moving Average Convergence Divergence (MACD).
    Returns a DataFrame with 'MACD', 'Signal', and 'Histogram' columns.
    """
    if not (fast_period > 0 and slow_period > 0 and signal_period > 0):
        logger.error("MACD periods must be positive.")
        raise ValueError("MACD periods must be positive.")
    if fast_period >= slow_period:
         logger.error("MACD fast_period must be less than slow_period.")
         raise ValueError("MACD fast_period must be less than slow_period.")
    if len(data) < slow_period:
        logger.warning(f"Data length ({len(data)}) insufficient for MACD slow period ({slow_period}). Returning NaNs.")
        # Create DataFrame with NaNs
        nan_series = pd.Series([np.nan] * len(data), index=data.index)
        return pd.DataFrame({'MACD': nan_series, 'Signal': nan_series, 'Histogram': nan_series})

    ema_fast = calculate_ema(data, fast_period)
    ema_slow = calculate_ema(data, slow_period)
    
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    # Create result DataFrame
    macd_df = pd.DataFrame({
        'MACD': macd_line,
        'Signal': signal_line,
        'Histogram': histogram
    }, index=data.index)
    
    # Set initial NaNs where calculation wasn't possible (up to slow_period + signal_period - 1)
    # macd_df[:slow_period + signal_period - 2] = np.nan # Be precise or just use fillna later
    
    return macd_df

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    # Create sample data
    sample_prices = np.random.randn(100).cumsum() + 50
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    price_series = pd.Series(sample_prices, index=dates)
    
    print("--- Sample Price Data ---")
    print(price_series.tail())
    
    print("\n--- SMA(10) ---")
    sma10 = calculate_sma(price_series, 10)
    print(sma10.tail())

    print("\n--- EMA(10) ---")
    ema10 = calculate_ema(price_series, 10)
    print(ema10.tail())
    
    print("\n--- RSI(14) ---")
    rsi14 = calculate_rsi(price_series, 14)
    print(rsi14.tail())
    
    print("\n--- MACD(12, 26, 9) ---")
    macd_data = calculate_macd(price_series, 12, 26, 9)
    print(macd_data.tail())
