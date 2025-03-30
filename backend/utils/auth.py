import os
import httpx # Using httpx for async requests
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from jose.utils import base64url_decode
import logging
from cachetools import TTLCache # For caching JWKS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") # Get the anon key
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise EnvironmentError("SUPABASE_URL or SUPABASE_ANON_KEY environment variable not set.")

# Ensure SUPABASE_URL doesn't have a trailing slash
if SUPABASE_URL.endswith('/'):
    SUPABASE_URL = SUPABASE_URL[:-1]

# Construct the JWKS URL - Reverting to the most standard path
JWKS_URL = f"{SUPABASE_URL}/auth/v1/jwks" 

# --- JWKS Caching ---
# Cache JWKS for 1 hour to avoid fetching on every request
jwks_cache = TTLCache(maxsize=1, ttl=3600)

# --- OAuth2 Scheme ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # Dummy tokenUrl

# --- JWKS Fetching ---
async def get_jwks():
    """Fetches and caches JWKS from Supabase."""
    cached_jwks = jwks_cache.get('jwks')
    if cached_jwks:
        logging.debug("Using cached JWKS.")
        return cached_jwks

    logging.info(f"Fetching JWKS from {JWKS_URL}")
    try:
        headers = {"apikey": SUPABASE_ANON_KEY} 
        logging.info(f"Attempting GET {JWKS_URL} with headers: {headers}") 
        async with httpx.AsyncClient() as client:
            response = await client.get(JWKS_URL, headers=headers) 
            logging.info(f"JWKS response status code: {response.status_code}") 
            response_text_preview = response.text[:500] + ('...' if len(response.text) > 500 else '')
            logging.debug(f"JWKS response text preview: {response_text_preview}") 
            
            response.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)
            
            logging.debug("Attempting to parse JWKS JSON...")
            jwks = response.json()
            logging.debug("Successfully parsed JWKS JSON.")
            
            jwks_cache['jwks'] = jwks # Cache the result
            return jwks
    except httpx.RequestError as e:
        logging.error(f"Error fetching JWKS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch authentication keys from provider.",
        )
    except Exception as e:
        logging.error(f"Unexpected error processing JWKS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing authentication keys.",
        )

# --- Token Verification ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency function to verify the JWT and return the user ID (sub).
    Inject this into endpoints that require authentication.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        jwks = await get_jwks()
        if not jwks or 'keys' not in jwks:
             logging.error("Invalid JWKS structure received.")
             raise credentials_exception

        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        if 'kid' not in unverified_header:
            logging.error("Token header missing 'kid'.")
            raise credentials_exception

        for key in jwks['keys']:
            if key['kid'] == unverified_header['kid']:
                rsa_key = {
                    'kty': key['kty'],
                    'kid': key['kid'],
                    'use': key['use'],
                    'n': key['n'],
                    'e': key['e']
                }
                break 

        if not rsa_key:
            logging.error(f"Unable to find matching key for kid {unverified_header['kid']} in JWKS.")
            raise credentials_exception

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"], 
            # options={"verify_aud": False}, 
            # issuer=f"{SUPABASE_URL}/auth/v1" 
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            logging.error("Token payload missing 'sub' (user ID).")
            raise credentials_exception
            
        logging.info(f"Successfully validated token for user_id: {user_id}")
        return user_id 

    except JWTError as e:
        logging.error(f"JWT Error: {e}")
        raise credentials_exception
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error during token validation: {e}")
        raise credentials_exception

# Example usage in an endpoint:
# from fastapi import APIRouter
# router = APIRouter()
# @router.get("/users/me")
# async def read_users_me(current_user_id: str = Depends(get_current_user)):
#     # current_user_id now contains the validated user's Supabase ID
#     return {"user_id": current_user_id}
