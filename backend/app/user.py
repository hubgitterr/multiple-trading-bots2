from fastapi import APIRouter, Depends, HTTPException, status
import logging # Import logging
from typing import Dict # For simple responses

# Import authentication dependency and user models
from ..utils.auth import get_current_user
from ..models.user_models import ApiKeysUpdate, UserProfile
from ..utils.db_client import get_supabase_backend_client # Import Supabase client getter

router = APIRouter()

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Initialize logger

@router.get("/me", response_model=UserProfile, tags=["User"], summary="Get current user profile")
async def get_user_profile(current_user_id: str = Depends(get_current_user)):
    """
    Retrieves the profile information for the currently authenticated user.
    Requires a valid JWT token in the Authorization header.
    """
    logger.info(f"Fetching profile for user_id: {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    try:
        # Fetch profile data from public.users table
        profile_response = await supabase.table('users').select('id, preferences, created_at, updated_at').eq('id', current_user_id).maybe_single().execute()

        if not profile_response.data:
             logger.warning(f"No profile found in public.users for user_id: {current_user_id}")
             # If profile doesn't exist, we should probably create it here or handle it gracefully
             # For now, let's return a default structure but log the warning
             # Ideally, a profile row should be created via trigger/function on Supabase auth signup
             return UserProfile(id=current_user_id, email="fetch_failed@example.com", preferences={})
             # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found.")

        # Combine data (using dummy email for now as getting auth email needs care)
        profile_data = profile_response.data
        # TODO: Fetch actual email securely if needed
        profile_data['email'] = "user@example.com" # Placeholder email

        return UserProfile(**profile_data)

    except Exception as e:
        logger.error(f"Database error fetching profile for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch user profile.")

@router.put("/api-keys", status_code=status.HTTP_200_OK, tags=["User"], summary="Update Binance API keys")
async def update_api_keys(
    api_keys: ApiKeysUpdate, 
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Updates the Binance API Key and Secret for the currently authenticated user.
    Stores the keys securely (implementation detail - ideally encrypted in DB).
    Requires a valid JWT token.
    """
    logger.info(f"Attempting to update API keys for user_id: {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    try:
        key = api_keys.binance_api_key.get_secret_value()
        secret = api_keys.binance_api_secret.get_secret_value()

        if not key or not secret:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API Key and Secret cannot be empty.")

        # --- Database Interaction ---
        logger.warning(f"Storing API keys directly in DB for user {current_user_id}. Consider encryption.")
        
        update_data = {
            'binance_api_key': key,
            'binance_api_secret': secret,
            'updated_at': 'now()' # Use database function to set timestamp
        }
        
        # Upsert the data: update if user_id exists, insert if it doesn't.
        # This ensures the user row exists before other operations need it.
        # Remove await from execute()
        response = supabase.table('users').upsert({**update_data, 'id': current_user_id}).execute()

        # Check if upsert was successful (supabase-py v2+ raises exceptions for errors)
        # If execute() completes without error, assume success.
        
        logger.info(f"Successfully executed upsert for API keys for user {current_user_id}")
        
    except HTTPException as http_exc:
        raise http_exc # Re-raise validation errors
    except Exception as e:
        logger.error(f"Error updating API keys for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while updating API keys.")

    return {"message": "API keys updated successfully."}

# Add other user-related endpoints here (e.g., update preferences)
