from fastapi import APIRouter, Depends, HTTPException, status
import logging
from typing import Dict # For simple responses

# Import authentication dependency and user models
from ..utils.auth import get_current_user
from ..models.user_models import ApiKeysUpdate, UserProfile
from ..utils.db_client import get_supabase_backend_client # Import Supabase client getter

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@router.get("/me", response_model=UserProfile, tags=["User"], summary="Get current user profile")
async def get_user_profile(current_user_id: str = Depends(get_current_user)):
    """
    Retrieves the profile information for the currently authenticated user.
    Requires a valid JWT token in the Authorization header.
    """
    logging.info(f"Fetching profile for user_id: {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    try:
        # Fetch user data from the 'users' table based on the authenticated user's ID
        # Assumes a 'users' table exists with an 'id' column matching auth.users.id
        # Also fetches email from auth.users table for completeness
        # Note: Adjust select columns as needed based on your actual 'users' table schema
        # We might need a trigger or function to populate the public.users table on signup.
        
        # First, get email from auth (requires service key or specific permissions)
        # This might fail if RLS prevents service role from reading auth.users directly
        # user_auth_info = await supabase.auth.admin.get_user_by_id(current_user_id) # Requires admin privileges
        # user_email = user_auth_info.user.email if user_auth_info.user else None
        
        # Fetch profile data from public.users table
        # RLS policy should allow user to read their own row
        # For backend calls using service key, we might need to impersonate the user or adjust RLS
        
        # Let's assume RLS allows service key read for now, or we adjust later
        # A safer approach might be to create a dedicated DB function (RPC)
        profile_response = await supabase.table('users').select('id, preferences, created_at, updated_at').eq('id', current_user_id).maybe_single().execute()

        if not profile_response.data:
             # If profile doesn't exist in public.users, maybe create it? Or return minimal info.
             # For now, raise 404 if no profile row exists.
             logger.warning(f"No profile found in public.users for user_id: {current_user_id}")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found.")

        # Combine data (using dummy email for now as getting auth email needs care)
        profile_data = profile_response.data
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
    logging.info(f"Attempting to update API keys for user_id: {current_user_id}")
    supabase = await get_supabase_backend_client()
    
    # Extract keys from the SecretStr model
    try:
        key = api_keys.binance_api_key.get_secret_value()
        secret = api_keys.binance_api_secret.get_secret_value()

        if not key or not secret:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API Key and Secret cannot be empty.")

        # --- Database Interaction ---
        # WARNING: Storing secrets directly is insecure. Consider encryption (e.g., pgsodium).
        logger.warning(f"Storing API keys directly in DB for user {current_user_id}. Consider encryption.")
        
        update_data = {
            'binance_api_key': key,
            'binance_api_secret': secret,
            'updated_at': 'now()' # Use database function to set timestamp
        }
        
        # Update the 'users' table for the specific user ID
        # RLS policy should allow user to update their own row.
        # If using service key, ensure RLS doesn't block or use RPC.
        response = await supabase.table('users').update(update_data).eq('id', current_user_id).execute()

        # Check if update was successful (e.g., if data was returned or no error)
        # Note: update() might return empty data even on success if returning='minimal'
        if response.data is None and response.error: # Check for explicit error
             logger.error(f"Supabase error updating API keys for user {current_user_id}: {response.error}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update API keys.")
        elif not response.data and not response.error:
             # This might happen if the user row didn't exist, handle as needed
             logger.warning(f"API key update for user {current_user_id} affected 0 rows (user might not exist in public.users).")
             # Optionally, upsert instead of update if profile might not exist
             # upsert_response = await supabase.table('users').upsert({**update_data, 'id': current_user_id}).execute()

        logger.info(f"Successfully updated API keys for user {current_user_id}")
        
    except HTTPException as http_exc:
        raise http_exc # Re-raise validation errors
    except Exception as e:
        logger.error(f"Error updating API keys for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while updating API keys.")

    # Important: Do NOT return the keys in the response!
    return {"message": "API keys updated successfully."}

# Add other user-related endpoints here (e.g., update preferences)
