from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional
import uuid

# Pydantic models for bot configuration and status

class BotConfigBase(BaseModel):
    """Base model for bot configuration, used for creation."""
    name: str = Field(..., min_length=1, max_length=100, description="User-defined name for the bot instance")
    bot_type: str = Field(..., description="Type of the bot ('momentum', 'grid', 'dca')")
    symbol: str = Field(..., description="Trading symbol (e.g., 'BTCUSDT')")
    config_params: Dict[str, Any] = Field(..., description="Bot-specific parameters (e.g., grid levels, indicator settings)")
    is_active: bool = Field(default=False, description="Whether the bot should be actively trading")

    @validator('bot_type')
    def bot_type_must_be_valid(cls, v):
        allowed_types = {'momentum', 'grid', 'dca'}
        if v not in allowed_types:
            raise ValueError(f"bot_type must be one of {allowed_types}")
        return v

    @validator('symbol')
    def symbol_to_uppercase(cls, v):
        return v.upper()

class BotConfigCreate(BotConfigBase):
    """Model used when creating a new bot configuration via API."""
    pass # Inherits all fields from Base

class BotConfigUpdate(BaseModel):
    """Model used when updating an existing bot configuration via API. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    config_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class BotConfigResponse(BotConfigBase):
    """Model representing a bot configuration returned by the API."""
    id: uuid.UUID = Field(..., description="Unique identifier for the bot configuration")
    user_id: uuid.UUID = Field(..., description="Identifier of the user who owns the bot")
    created_at: Optional[Any] = None # Using Any to avoid datetime import issues initially
    updated_at: Optional[Any] = None

    class Config:
        from_attributes = True # Pydantic V2 equivalent of orm_mode

class BotStatusResponse(BaseModel):
    """Model representing the runtime status of a bot instance."""
    bot_id: str = Field(..., description="Unique identifier for the bot configuration")
    name: str = Field(..., description="Name of the bot instance")
    type: str = Field(..., description="Type of the bot")
    symbol: str = Field(..., description="Trading symbol")
    is_active: bool = Field(..., description="Configuration status (enabled/disabled)")
    is_running: bool = Field(..., description="Actual runtime status (processing/idle)")
    config_params: Dict[str, Any] = Field(..., description="Current configuration parameters")
    # Add more status fields as needed from BaseTradingBot.get_status()
