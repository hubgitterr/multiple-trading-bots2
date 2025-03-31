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
        response = supabase_client.table('bot_configs').select("*").eq('id', str(bot_id)).eq('user_id', user_id).maybe_single().execute()
        if response.data:
             response.data['id'] = uuid.UUID(response.data['id'])
             response.data['user_id'] = uuid.UUID(response.data['user_id'])
             return response.data
        else:
            logger.warning(f"Bot config {bot_id} not found for user {user_id}.")
            return None
    except Exception as e:
        logger.error(f"Error fetching bot config {bot_id} for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error fetching bot configuration.")

async def _create_bot_instance(config: Dict[str, Any], user_id: str) -> BaseTradingBot:
    """Creates the appropriate bot instance based on bot_type."""
    bot_type = config.get("bot_type")
    logger.info(f"Creating instance for bot type: {bot_type}")
    
    from ..bots.momentum_bot import MomentumTradingBot
    from ..bots.grid_bot import GridTradingBot 
    from ..bots.dca_bot import DCATradingBot 
    
    if bot_type == "momentum": return MomentumTradingBot(config, user_id) 
    elif bot_type == "grid": return GridTradingBot(config, user_id) 
    elif bot_type == "dca": return DCATradingBot(config, user_id) 
    else: raise ValueError(f"Unsupported bot type: {bot_type}")

# --- API Endpoints ---

@router.post("", response_model=BotConfigResponse, status_code=status.HTTP_201_CREATED, tags=["Bots"], summary="Create new bot configuration")
async def create_bot_configuration(
    bot_data: BotConfigCreate,
    current_user_id: str = Depends(get_current_user)
):
    logger.info(f"Received request to create bot config: {bot_data.name} ({bot_data.bot_type}) for user {current_user_id}")
    supabase = await get_supabase_backend_client()
    user_uuid = uuid.UUID(current_user_id) # Convert to UUID
    
    try:
        # --- Ensure user exists in public.users table ---
        # Attempt an upsert with minimal data just to ensure the row exists
        # This is slightly redundant if the trigger/previous upsert worked, but adds robustness
        # Ensure the user exists in the public.users table before creating a bot config
        try:
             user_upsert_data = {'id': str(user_uuid)} # Use STRING representation for upsert
             # Ensure execute() is called correctly for the upsert check
             upsert_response = supabase.table('users').upsert(user_upsert_data).execute()
             # Optional: Check upsert_response if needed, though errors should raise exceptions
             logger.info(f"Ensured user row exists via upsert check for {user_uuid}")
        except Exception as user_e:
             # Log the error but proceed, the main insert might still work if trigger ran
             logger.error(f"Error during user upsert check for {user_uuid}: {user_e}", exc_info=True)
             # Raise a specific error if this check is critical
             # raise HTTPException(status_code=500, detail="Failed to verify user profile existence.")

        # --- Insert Bot Config ---
             supabase.table('users').upsert(user_upsert_data).execute()
             logger.info(f"Ensured user row exists for {user_uuid}")
        except Exception as user_e:
             # Log the error but proceed, the main insert might still work if trigger ran
             logger.error(f"Error during user upsert check for {user_uuid}: {user_e}", exc_info=True)
             # Do not raise here, let the bot insert fail if user truly doesn't exist

        # --- Insert Bot Config ---
        insert_data = bot_data.dict()
        # Use string representation of UUID for insert data
        insert_data['user_id'] = str(user_uuid) 
        
        response = supabase.table('bot_configs').insert(insert_data).execute()
        
        # supabase-py v2 raises APIError on failure, so checking response.data might be sufficient
        # if not response.data: # This check might be redundant if APIError is raised
        #     logger.error(f"Failed to insert bot config (no data returned): {getattr(response, 'error', 'Unknown error')}")
        #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save bot configuration.")
            
        created_config = response.data[0] 
        created_config['id'] = uuid.UUID(created_config['id'])
        created_config['user_id'] = uuid.UUID(str(created_config['user_id'])) # Ensure it's UUID
        
        logger.info(f"Successfully created bot config {created_config['id']} for user {current_user_id}")
        return BotConfigResponse(**created_config)
        
    except Exception as e:
        # Catch potential APIError from execute() or other errors
        logger.error(f"Error creating bot config for user {current_user_id}: {e}", exc_info=True)
        # Check if it's the foreign key error specifically
        if "violates foreign key constraint" in str(e):
             detail = "Failed to create bot: User profile not found. Please try saving settings first."
             status_code = status.HTTP_409_CONFLICT
        else:
             detail = "Error creating bot configuration."
             status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=status_code, detail=detail)

@router.get("", response_model=List[BotConfigResponse], tags=["Bots"], summary="List user's bot configurations")
async def list_bot_configurations(current_user_id: str = Depends(get_current_user)):
    logger.info(f"Fetching all bot configurations for user {current_user_id}")
    supabase = await get_supabase_backend_client()
    try:
        response = supabase.table('bot_configs').select("*").eq('user_id', current_user_id).execute()
        # supabase-py v2 raises error on failure, so check data directly
        configs_data = []
        if response.data:
            for config in response.data:
                 config['id'] = uuid.UUID(config['id'])
                 config['user_id'] = uuid.UUID(str(config['user_id']))
                 configs_data.append(BotConfigResponse(**config))
        return configs_data
    except Exception as e:
        logger.error(f"Error fetching bot configs for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching bot configurations.")

@router.get("/{bot_id}", response_model=BotConfigResponse, tags=["Bots"], summary="Get specific bot configuration")
async def get_bot_configuration(bot_id: uuid.UUID, current_user_id: str = Depends(get_current_user)):
    logger.info(f"Fetching bot configuration {bot_id} for user {current_user_id}")
    config = await _get_bot_config_from_db(bot_id, current_user_id) 
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration with ID {bot_id} not found or access denied.")
    return BotConfigResponse(**config)

@router.put("/{bot_id}", response_model=BotConfigResponse, tags=["Bots"], summary="Update bot configuration")
async def update_bot_configuration(
    bot_id: uuid.UUID,
    update_data: BotConfigUpdate,
    current_user_id: str = Depends(get_current_user)
):
    logger.info(f"Updating bot configuration {bot_id} for user {current_user_id} with data: {update_data.dict(exclude_unset=True)}")
    supabase = await get_supabase_backend_client()
    update_payload = update_data.dict(exclude_unset=True) 
    if not update_payload: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided.")
    update_payload['updated_at'] = 'now()' 
    try:
        response = supabase.table('bot_configs').update(update_payload).eq('id', str(bot_id)).eq('user_id', current_user_id).execute()
        # Check if data exists in response (might be empty if row not found and returning='minimal')
        if not response.data:
             existing_check = await _get_bot_config_from_db(bot_id, current_user_id, supabase)
             if not existing_check: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")
             else: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update bot configuration (no data returned).")

        updated_config = response.data[0]
        updated_config['id'] = uuid.UUID(updated_config['id'])
        updated_config['user_id'] = uuid.UUID(str(updated_config['user_id']))
        
        bot_instance = running_bots.get(str(bot_id))
        if bot_instance and 'config_params' in update_payload:
            bot_instance.update_config(update_payload['config_params'])

        logger.info(f"Successfully updated bot config {bot_id}")
        return BotConfigResponse(**updated_config)
    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        logger.error(f"Error updating bot config {bot_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating bot configuration.")

@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Bots"], summary="Delete bot configuration")
async def delete_bot_configuration(
    bot_id: uuid.UUID,
    current_user_id: str = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    logger.info(f"Request to delete bot configuration {bot_id} for user {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    bot_instance = running_bots.get(str(bot_id))
    if bot_instance:
        logger.info(f"Bot instance {bot_id} is running. Stopping before deletion.")
        await bot_instance.stop() 
        if str(bot_id) in running_bots: del running_bots[str(bot_id)] 

    try:
        response = supabase.table('bot_configs').delete().eq('id', str(bot_id)).eq('user_id', current_user_id).execute()
        # Check if deletion returned data (it should if successful)
        if not response.data:
             existing_check = await _get_bot_config_from_db(bot_id, current_user_id, supabase)
             if not existing_check: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")
             else: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete bot configuration (no data returned).")
        logger.info(f"Successfully deleted bot configuration {bot_id}")
    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        logger.error(f"Error deleting bot config {bot_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting bot configuration.")
    return None 

@router.post("/{bot_id}/start", status_code=status.HTTP_200_OK, tags=["Bots Control"], summary="Start a trading bot")
async def start_bot(
    bot_id: uuid.UUID, 
    current_user_id: str = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    logger.info(f"Request to start bot {bot_id} for user {current_user_id}")
    if str(bot_id) in running_bots: return {"message": "Bot is already running."}
    config = await _get_bot_config_from_db(bot_id, current_user_id)
    if not config: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")
    if not config.get('is_active'): raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Bot {bot_id} is not marked as active.")
    try:
        bot_instance = await _create_bot_instance(config, current_user_id)
        running_bots[str(bot_id)] = bot_instance
        background_tasks.add_task(bot_instance.start) 
        logger.info(f"Bot {bot_id} added to running instances and start initiated.")
        return {"message": f"Bot {config.get('name')} ({bot_id}) start initiated."}
    except ValueError as e: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create or start bot instance {bot_id}: {e}", exc_info=True)
        if str(bot_id) in running_bots: del running_bots[str(bot_id)]
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start bot {bot_id}.")

@router.post("/{bot_id}/stop", status_code=status.HTTP_200_OK, tags=["Bots Control"], summary="Stop a trading bot")
async def stop_bot(
    bot_id: uuid.UUID, 
    current_user_id: str = Depends(get_current_user), 
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    logger.info(f"Request to stop bot {bot_id} for user {current_user_id}")
    config = await _get_bot_config_from_db(bot_id, current_user_id) # Verify ownership
    if not config: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")
    bot_instance = running_bots.get(str(bot_id))
    if not bot_instance: return {"message": f"Bot {bot_id} is not running."}
    background_tasks.add_task(bot_instance.stop)
    del running_bots[str(bot_id)] 
    logger.info(f"Bot {bot_id} removed from running instances and stop initiated.")
    return {"message": f"Bot {bot_id} stop initiated."}

@router.get("/{bot_id}/status", response_model=BotStatusResponse, tags=["Bots Control"], summary="Get bot runtime status")
async def get_bot_status(bot_id: uuid.UUID, current_user_id: str = Depends(get_current_user)):
    logger.debug(f"Request for status of bot {bot_id} by user {current_user_id}")
    config = await _get_bot_config_from_db(bot_id, current_user_id) # Verify ownership
    if not config: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {bot_id} not found or access denied.")
    bot_instance = running_bots.get(str(bot_id))
    if not bot_instance:
        return BotStatusResponse(
            bot_id=str(bot_id), name=config.get('name'), type=config.get('bot_type'),
            symbol=config.get('symbol'), is_active=config.get('is_active'), 
            is_running=False, config_params=config.get('config_params')
        )
    status_data = bot_instance.get_status()
    return BotStatusResponse(**status_data)

# --- Backtesting Endpoint ---
class BacktestRequest(BaseModel):
    bot_config_id: uuid.UUID
    start_date: str 
    end_date: str   

@router.post("/backtest", response_model=Optional[BacktestResult], tags=["Backtesting"], summary="Run backtest for a bot configuration")
async def trigger_backtest(
    request: BacktestRequest,
    current_user_id: str = Depends(get_current_user)
):
    logger.info(f"Received backtest request for bot {request.bot_config_id} from {request.start_date} to {request.end_date}")
    bot_config = await _get_bot_config_from_db(request.bot_config_id, current_user_id)
    if not bot_config: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot configuration {request.bot_config_id} not found or access denied.")
    try:
        backtest_results = await run_backtest(bot_config=bot_config, start_date=request.start_date, end_date=request.end_date)
        if backtest_results is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Backtest execution failed. Check server logs.")
        logger.info(f"Backtest for bot {request.bot_config_id} completed.")
        return backtest_results
    except HTTPException as http_exc: raise http_exc 
    except Exception as e:
        logger.error(f"Unexpected error during backtest trigger for bot {request.bot_config_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during backtest.")
