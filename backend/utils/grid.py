import numpy as np
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

def calculate_grid_levels(
    lower_bound: float, 
    upper_bound: float, 
    num_grids: int, 
    mode: str = 'arithmetic'
) -> List[float]:
    """
    Calculates the price levels for a grid trading strategy.

    Args:
        lower_bound (float): The lower price boundary of the grid.
        upper_bound (float): The upper price boundary of the grid.
        num_grids (int): The number of grid lines (levels) to create.
        mode (str): The mode for calculating levels ('arithmetic' or 'geometric').

    Returns:
        List[float]: A sorted list of grid price levels.
        
    Raises:
        ValueError: If inputs are invalid (e.g., bounds reversed, num_grids <= 0).
    """
    if lower_bound >= upper_bound:
        logger.error("Grid lower bound must be less than upper bound.")
        raise ValueError("Grid lower bound must be less than upper bound.")
    if num_grids <= 0:
        logger.error("Number of grids must be positive.")
        raise ValueError("Number of grids must be positive.")
        
    levels = []
    if mode == 'arithmetic':
        if num_grids == 1:
             # Special case: single grid line often means trading around a central price
             # Or could place it at the midpoint. Let's place at midpoint for now.
             levels = [(lower_bound + upper_bound) / 2]
        else:
            step = (upper_bound - lower_bound) / (num_grids -1) if num_grids > 1 else 0
            levels = [lower_bound + i * step for i in range(num_grids)]
            
    elif mode == 'geometric':
        if lower_bound <= 0:
             logger.error("Geometric grid requires lower_bound > 0.")
             raise ValueError("Geometric grid requires lower_bound > 0.")
        if num_grids == 1:
             levels = [np.sqrt(lower_bound * upper_bound)] # Geometric mean
        else:
             # Ratio between consecutive levels
             ratio = (upper_bound / lower_bound) ** (1 / (num_grids - 1)) if num_grids > 1 else 1
             levels = [lower_bound * (ratio ** i) for i in range(num_grids)]
             
    else:
        logger.error(f"Unsupported grid mode: {mode}")
        raise ValueError(f"Unsupported grid mode: {mode}. Choose 'arithmetic' or 'geometric'.")

    # Ensure bounds are included precisely if needed, handle potential float inaccuracies
    levels = sorted(list(set(levels))) # Remove duplicates and sort
    logger.info(f"Calculated {len(levels)} grid levels using {mode} mode between {lower_bound} and {upper_bound}.")
    
    # Optional: Round levels to appropriate precision based on asset?
    # levels = [round(level, price_precision) for level in levels]
    
    return levels

def calculate_order_quantities(
    total_investment: float,
    grid_levels: List[float],
    current_price: float,
    mode: str = 'equal_value' # or 'equal_quantity'
) -> List[Tuple[float, float]]:
    """
    Calculates the quantity to buy/sell at each grid level.
    (Simplified initial version - assumes placing buy orders below current price)

    Args:
        total_investment (float): The total amount of quote currency to invest across the grid.
        grid_levels (List[float]): The calculated grid price levels.
        current_price (float): The current market price, used to determine which levels get buy orders.
        mode (str): How to distribute quantity ('equal_value' or 'equal_quantity').

    Returns:
        List[Tuple[float, float]]: A list of tuples (price_level, quantity_to_buy). 
                                    Only includes levels below the current price.
    """
    if total_investment <= 0:
        raise ValueError("Total investment must be positive.")
        
    buy_levels = [level for level in grid_levels if level < current_price]
    num_buy_orders = len(buy_levels)

    if num_buy_orders == 0:
        logger.warning("No grid levels below current price. No buy orders calculated.")
        return []

    orders = []
    if mode == 'equal_value':
        # Each buy order uses an equal amount of the quote currency
        value_per_order = total_investment / num_buy_orders
        for level in buy_levels:
            quantity = value_per_order / level
            orders.append((level, quantity))
            
    elif mode == 'equal_quantity':
        # Requires calculating total quantity first, more complex if value is fixed.
        # Let's stick to equal_value for simplicity first.
        # If we wanted equal quantity of BASE asset per grid:
        # 1. Calculate total value needed: sum(level * quantity_per_level for level in buy_levels)
        # 2. Adjust quantity_per_level based on total_investment constraint.
        # This is less common for basic grids.
        logger.warning("Equal quantity mode not fully implemented yet. Using equal value.")
        value_per_order = total_investment / num_buy_orders
        for level in buy_levels:
            quantity = value_per_order / level
            orders.append((level, quantity))
            
    else:
         raise ValueError("Unsupported order quantity mode.")

    logger.info(f"Calculated {len(orders)} buy orders for grid.")
    return orders


# --- Example Usage ---
if __name__ == '__main__':
    lower = 100.0
    upper = 120.0
    grids = 5
    current = 112.0
    investment = 1000.0

    print(f"--- Arithmetic Grid ({lower}-{upper}, {grids} levels) ---")
    arith_levels = calculate_grid_levels(lower, upper, grids, 'arithmetic')
    print("Levels:", [round(l, 2) for l in arith_levels])
    arith_orders = calculate_order_quantities(investment, arith_levels, current, 'equal_value')
    print("Buy Orders (Price, Qty):", [(round(p, 2), round(q, 5)) for p, q in arith_orders])


    print(f"\n--- Geometric Grid ({lower}-{upper}, {grids} levels) ---")
    geom_levels = calculate_grid_levels(lower, upper, grids, 'geometric')
    print("Levels:", [round(l, 2) for l in geom_levels])
    geom_orders = calculate_order_quantities(investment, geom_levels, current, 'equal_value')
    print("Buy Orders (Price, Qty):", [(round(p, 2), round(q, 5)) for p, q in geom_orders])
