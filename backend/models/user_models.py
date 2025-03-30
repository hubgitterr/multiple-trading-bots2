from pydantic import BaseModel, Field, SecretStr
from typing import Optional

# Pydantic models for user-related data structures

class ApiKeysUpdate(BaseModel):
    """Model for updating Binance API keys."""
    binance_api_key: SecretStr = Field(..., description="User's Binance API Key")
    binance_api_secret: SecretStr = Field(..., description="User's Binance API Secret")

    class Config:
        # Example configuration if needed, e.g., for ORM mode
        # orm_mode = True 
        pass

class UserProfile(BaseModel):
    """Model representing basic user profile data (excluding sensitive info)."""
    id: str # Supabase User ID (UUID as string)
    email: Optional[str] = None # User's email
    preferences: Optional[dict] = None # User preferences JSON

    class Config:
        from_attributes = True # Pydantic V2 equivalent of orm_mode

# Add other user-related models here as needed (e.g., PreferencesUpdate)
