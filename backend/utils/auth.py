import os
import httpx # Using httpx for async requests
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
# from jose.utils import base64url_decode # Not needed for HS256
import logging
# from cachetools import TTLCache # Not needed for HS256

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") # No longer needed for JWKS fetch
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET") # Get the JWT Secret

if not SUPABASE_URL or not SUPABASE_JWT_SECRET:
    raise EnvironmentError("SUPABASE_URL or SUPABASE_JWT_SECRET environment variable not set.")

# JWKS URL no longer needed
# JWKS_URL = f"{SUPABASE_URL}/auth/v1/jwks" 

# JWKS Cache no longer needed
# jwks_cache = TTLCache(maxsize=1, ttl=3600)

# --- OAuth2 Scheme ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # Dummy tokenUrl

# --- JWKS Fetching Function (No longer used by get_current_user) ---
# async def get_jwks():
#     """Fetches and caches JWKS from Supabase."""
#     # ... (previous JWKS fetching logic removed) ...
#     pass # Keep function defined maybe, or remove entirely if not used elsewhere

# --- Token Verification (Using JWT Secret) ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency function to verify the JWT using the Supabase JWT Secret 
    and return the user ID (sub).
    Inject this into endpoints that require authentication.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify the token signature and claims using the JWT Secret
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"], 
            audience="authenticated" # Specify expected audience for Supabase JWTs
            # issuer=f"{SUPABASE_URL}/auth/v1" # Optionally validate issuer
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            logging.error("Token payload missing 'sub' (user ID).")
            raise credentials_exception
            
        logging.info(f"Successfully validated token for user_id: {user_id} using JWT Secret.")
        return user_id # Return the user ID (subject)

    except JWTError as e:
        logging.error(f"JWT Error: {e}")
        raise credentials_exception
    except Exception as e:
        logging.error(f"Unexpected error during token validation: {e}")
        raise credentials_exception

# Example usage remains the same
# from fastapi import APIRouter
# router = APIRouter()
# @router.get("/users/me")
# async def read_users_me(current_user_id: str = Depends(get_current_user)):
#     # current_user_id now contains the validated user's Supabase ID
#     return {"user_id": current_user_id}
