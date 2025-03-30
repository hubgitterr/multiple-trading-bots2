import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Dict, Any
import uuid
import logging

# Import models, base bot class, and auth dependency
from ..models.bot_models import (
    BotConfigCreate, BotConfigUpdate, BotConfigResponse, BotStatusResponse
)
from ..bots.base_bot import BaseTradingBot
from ..utils.auth import get_current_user
from ..utils.db_client import get_supabase_backend_client # Import Supabase client
from pydantic import BaseModel # For backtest request body
from ..utils.backtest import run_backtest, BacktestResult # Import backtesting function and result type
from typing import Optional # Needed for Optional in helper function signature

# --- Bot Instance Management (In-Memory) ---
# Simple in-memory storage for running bot instances.
# Key: bot_id (str), Value: BaseTradingBot instance
# NOTE: This is suitable for single-process local development ONLY.
# For production/scaling, use a distributed cache (Redis) or task queue (Celery).
running_bots: Dict[str, BaseTradingBot] = {}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter()

# --- Helper Function ---
async def _get_bot_config_from_db(bot_id: uuid.UUID, user_id: str, supabase_client = None) -> Optional[Dict[str, Any]]:
    """Fetches bot config from DB, ensuring user ownership."""
    if not supabase_client:
        supabase_client = await get_supabase_backend_client()
    try:
        # RLS policy should enforce user_id match
        response = await supabase_client.table('bot_configs').select("*").eq('id', str(bot_id)).eq('user_id', user_id).maybe_single().execute()
        if response.data:
            # Convert UUIDs back if needed, though Pydantic might handle it
             response.data['id'] = uuid.UUID(response.data['id'])
             response.data['user_id'] = uuid.UUID(response.data['user_id'])
             return response.data
        else:
            logger.warning(f"Bot config {bot_id} not found for user {user_id}.")
            return None
    except Exception as e:
        logger.error(f"Error fetching bot config {bot_id} for user {user_id}: {e}", exc_info=True)
        # Raise or return None depending on desired error handling
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error fetching bot configuration.")

async def _create_bot_instance(config: Dict[str, Any], user_id: str) -> BaseTradingBot:
    """Creates the appropriate bot instance based on bot_type."""
    bot_type = config.get("bot_type")
    logger.info(f"Creating instance for bot type: {bot_type}")
    
    # Import specific bot classes
    from ..bots.momentum_bot import MomentumTradingBot
    from ..bots.grid_bot import GridTradingBot 
    from ..bots.dca_bot import DCATradingBot 
    
    if bot_type == "momentum":
        return MomentumTradingBot(config, user_id) 
    elif bot_type == "grid":
        return GridTradingBot(config, user_id) 
    elif bot_type == "dca":
        return DCATradingBot(config, user_id) # Use the actual class now
    else:
        logger.error(f"Unknown bot type '{bot_type}' requested.")
        raise ValueError(f"Unsupported bot type: {bot_type}")

# --- API Endpoints ---

@router.post("", response_model=BotConfigResponse, status_code=status.HTTP_201_CREATED, tags=["Bots"], summary="Create new bot configuration")
async def create_bot_configuration(
    bot_data: BotConfigCreate,
    current_user_id: str = Depends(get_current_user)
):
    """
    Creates a new trading bot configuration in the database for the authenticated user.
    Does not start the bot instance.
    """
    logger.info(f"Received request to create bot config: {bot_data.name} ({bot_data.bot_type}) for user {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    try:
        insert_data = bot_data.dict()
        insert_data['user_id'] = current_user_id # Add the user ID
        
        response = await supabase.table('bot_configs').insert(insert_data).execute()
        
        if not response.data:
            logger.error(f"Failed to insert bot config: {response.error}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save bot configuration.")
            
        created_config = response.data[0] # Supabase returns list
        # Convert UUIDs back if needed by Pydantic model
        created_config['id'] = uuid.UUID(created_config['id'])
        created_config['user_id'] = uuid.UUID(created_config['user_id'])
        
        logger.info(f"Successfully created bot config {created_config['id']} for user {current_user_id}")
        return BotConfigResponse(**created_config)
        
    except Exception as e:
        logger.error(f"Error creating bot config for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating bot configuration.")

@router.get("", response_model=List[BotConfigResponse], tags=["Bots"], summary="List user's bot configurations")
async def list_bot_configurations(current_user_id: str = Depends(get_current_user)):
    """
    Retrieves all bot configurations belonging to the authenticated user.
    """
    logger.info(f"Fetching all bot configurations for user {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    try:
        # RLS policy should handle filtering by user_id
        response = await supabase.table('bot_configs').select("*").eq('user_id', current_user_id).execute()
        
        if response.data is None: # Check for None explicitly
             logger.error(f"Supabase error fetching bot configs for user {current_user_id}: {response.error}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch bot configurations.")

        # Convert UUIDs before creating response models
        configs_data = []
        for config in response.data:
             config['id'] = uuid.UUID(config['id'])
             config['user_id'] = uuid.UUID(config['user_id'])
             configs_data.append(BotConfigResponse(**config))
             
        return configs_data
        
    except Exception as e:
        logger.error(f"Error fetching bot configs for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching bot configurations.")

@router.get("/{bot_id}", response_model=BotConfigResponse, tags=["Bots"], summary="Get specific bot configuration")
async def get_bot_configuration(bot_id: uuid.UUID, current_user_id: str = Depends(get_current_user)):
    """
    Retrieves the details of a specific bot configuration by its ID.
    Ensures the bot belongs to the authenticated user.
    """
    logger.info(f"Fetching bot configuration {bot_id} for user {current_user_id}")
    # Use the helper function which includes error handling
    config = await _get_bot_config_from_db(bot_id, current_user_id) 
    if not config:
        # _get_bot_config_from_db raises HTTPException on DB error, so this means not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration with ID {bot_id} not found or access denied.")
    return BotConfigResponse(**config)

@router.put("/{bot_id}", response_model=BotConfigResponse, tags=["Bots"], summary="Update bot configuration")
async def update_bot_configuration(
    bot_id: uuid.UUID,
    update_data: BotConfigUpdate,
    current_user_id: str = Depends(get_current_user)
):
    """
    Updates an existing bot configuration (name, parameters, active status).
    Ensures the bot belongs to the authenticated user.
    If the bot is running and `is_active` is changed, it might affect its state (start/stop logic is separate).
    """
    logger.info(f"Updating bot configuration {bot_id} for user {current_user_id} with data: {update_data.dict(exclude_unset=True)}")
    supabase = await get_supabase_backend_client()
    
    update_payload = update_data.dict(exclude_unset=True) # Get only fields that were provided
    if not update_payload:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided.")
         
    update_payload['updated_at'] = 'now()' # Update timestamp

    try:
        # RLS policy should enforce user_id match
        response = await supabase.table('bot_configs').update(update_payload).eq('id', str(bot_id)).eq('user_id', current_user_id).execute()

        if not response.data:
             # Could be not found or another error
             logger.error(f"Failed to update bot config {bot_id} for user {current_user_id}: {response.error}")
             # Check if it was a 'not found' scenario specifically
             existing_check = await _get_bot_config_from_db(bot_id, current_user_id, supabase)
             if not existing_check:
                  raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")
             else: # Some other update error
                  raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update bot configuration.")

        updated_config = response.data[0]
        updated_config['id'] = uuid.UUID(updated_config['id'])
        updated_config['user_id'] = uuid.UUID(updated_config['user_id'])
        
        # Update running instance if necessary
        bot_instance = running_bots.get(str(bot_id))
        if bot_instance and 'config_params' in update_payload:
            bot_instance.update_config(update_payload['config_params'])
        # Note: is_active changes are handled by start/stop endpoints, not directly here.

        logger.info(f"Successfully updated bot config {bot_id}")
        return BotConfigResponse(**updated_config)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error updating bot config {bot_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating bot configuration.")

@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Bots"], summary="Delete bot configuration")
async def delete_bot_configuration(
    bot_id: uuid.UUID,
    current_user_id: str = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Deletes a bot configuration from the database.
    If the bot instance is running, it will be stopped first.
    Ensures the bot belongs to the authenticated user.
    """
    logger.info(f"Request to delete bot configuration {bot_id} for user {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    # Stop the bot if it's running (do this first)
    bot_instance = running_bots.get(str(bot_id))
    if bot_instance:
        logger.info(f"Bot instance {bot_id} is running. Stopping before deletion.")
        await bot_instance.stop() # Await stop completion before deleting DB record
        if str(bot_id) in running_bots: # Check if stop was successful before deleting key
             del running_bots[str(bot_id)] 

    try:
        # RLS policy should enforce user_id match
        response = await supabase.table('bot_configs').delete().eq('id', str(bot_id)).eq('user_id', current_user_id).execute()

        # Check if deletion was successful (data should be returned on success)
        if not response.data:
             # Could be not found or another error
             logger.error(f"Failed to delete bot config {bot_id} for user {current_user_id}: {response.error}")
             # Check if it was a 'not found' scenario
             existing_check = await _get_bot_config_from_db(bot_id, current_user_id, supabase)
             if not existing_check:
                  raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")
             else: # Some other delete error
                  raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete bot configuration.")

        logger.info(f"Successfully deleted bot configuration {bot_id}")
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error deleting bot config {bot_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting bot configuration.")

    # Return 204 No Content on success
    return None # Return 204 No Content on success

@router.post("/{bot_id}/start", status_code=status.HTTP_200_OK, tags=["Bots Control"], summary="Start a trading bot")
async def start_bot(
    bot_id: uuid.UUID, 
    current_user_id: str = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Starts a specific trading bot instance based on its saved configuration.
    Loads configuration, creates the bot object, and starts its execution loop.
    """
    logger.info(f"Request to start bot {bot_id} for user {current_user_id}")
    
    if str(bot_id) in running_bots:
        logger.warning(f"Bot {bot_id} is already running or starting.")
        return {"message": "Bot is already running."}

    config = await _get_bot_config_from_db(bot_id, current_user_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")

    if not config.get('is_active'):
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Bot {bot_id} is not marked as active in configuration. Activate it first.")

    try:
        bot_instance = await _create_bot_instance(config, current_user_id)
        running_bots[str(bot_id)] = bot_instance
        # Start the bot in the background
        background_tasks.add_task(bot_instance.start) 
        logger.info(f"Bot {bot_id} added to running instances and start initiated.")
        return {"message": f"Bot {config.get('name')} ({bot_id}) start initiated."}
    except ValueError as e: # Catch specific errors like unsupported bot type
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create or start bot instance {bot_id}: {e}", exc_info=True)
        if str(bot_id) in running_bots: # Clean up if instance was added but failed to start
            del running_bots[str(bot_id)]
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start bot {bot_id}.")

@router.post("/{bot_id}/stop", status_code=status.HTTP_200_OK, tags=["Bots Control"], summary="Stop a trading bot")
async def stop_bot(
    bot_id: uuid.UUID, 
    current_user_id: str = Depends(get_current_user), # Ensure user owns the bot
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Stops a specific running trading bot instance gracefully.
    """
    logger.info(f"Request to stop bot {bot_id} for user {current_user_id}")
    
    # Verify ownership even if just stopping (using dummy fetch for now)
    config = await _get_bot_config_from_db(bot_id, current_user_id)
    if not config:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")

    bot_instance = running_bots.get(str(bot_id))
    if not bot_instance:
        logger.warning(f"Bot {bot_id} is not currently running.")
        return {"message": f"Bot {bot_id} is not running."}

    # Run stop in background
    background_tasks.add_task(bot_instance.stop)
    # Remove from running list immediately - stop task handles actual shutdown
    del running_bots[str(bot_id)] 
    logger.info(f"Bot {bot_id} removed from running instances and stop initiated.")
    
    return {"message": f"Bot {bot_id} stop initiated."}

@router.get("/{bot_id}/status", response_model=BotStatusResponse, tags=["Bots Control"], summary="Get bot runtime status")
async def get_bot_status(bot_id: uuid.UUID, current_user_id: str = Depends(get_current_user)):
    """
    Retrieves the current runtime status of a specific bot instance.
    Ensures the bot belongs to the authenticated user.
    """
    logger.debug(f"Request for status of bot {bot_id} by user {current_user_id}")
    
    # Verify ownership first
    config = await _get_bot_config_from_db(bot_id, current_user_id)
    if not config:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")

    bot_instance = running_bots.get(str(bot_id))
    if not bot_instance:
        # If not in memory, return status based on config (not running)
        return BotStatusResponse(
            bot_id=str(bot_id), name=config.get('name'), type=config.get('bot_type'),
            symbol=config.get('symbol'), is_active=config.get('is_active'), 
            is_running=False, config_params=config.get('config_params')
        )
    
    # If running, get status from the instance
    status_data = bot_instance.get_status()
    return BotStatusResponse(**status_data)


# --- Backtesting Endpoint ---

class BacktestRequest(BaseModel):
    """Request body for initiating a backtest."""
    bot_config_id: uuid.UUID
    start_date: str # Expecting format like "1 Jan, 2023" or ISO YYYY-MM-DD
    end_date: str   # Expecting format like "31 Dec, 2023" or ISO YYYY-MM-DD

@router.post("/backtest", response_model=Optional[BacktestResult], tags=["Backtesting"], summary="Run backtest for a bot configuration")
async def trigger_backtest(
    request: BacktestRequest,
    current_user_id: str = Depends(get_current_user)
):
    """
    Triggers a backtest simulation for a specified bot configuration over a given date range.
    """
    logger.info(f"Received backtest request for bot {request.bot_config_id} from {request.start_date} to {request.end_date}")
    
    # 1. Fetch the bot configuration to ensure user owns it and get params
    bot_config = await _get_bot_config_from_db(request.bot_config_id, current_user_id)
    if not bot_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {request.bot_config_id} not found or access denied.")

    # 2. Run the backtest function (which includes fetching data)
    try:
        # Note: Backtesting can be long-running. For production, consider using background tasks (e.g., Celery)
        # and providing a way to check status and retrieve results later.
        # For now, run it directly and wait.
        backtest_results = await run_backtest(
            bot_config=bot_config, 
            start_date=request.start_date, 
            end_date=request.end_date
        )
        
        if backtest_results is None:
             # run_backtest handles logging errors internally
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Backtest execution failed. Check server logs.")
             
        logger.info(f"Backtest for bot {request.bot_config_id} completed.")
        return backtest_results

    except HTTPException as http_exc:
        raise http_exc # Re-raise specific HTTP errors
    except Exception as e:
        logger.error(f"Unexpected error during backtest trigger for bot {request.bot_config_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during backtest.")
