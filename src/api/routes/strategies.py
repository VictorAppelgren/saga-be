"""Strategy API Routes"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from src.storage.strategy_manager import StrategyStorageManager

router = APIRouter(prefix="/api", tags=["strategies"])
storage = StrategyStorageManager()


# Models
class StrategyListItem(BaseModel):
    id: str
    asset: str
    target: str
    updated_at: str
    has_analysis: bool


class StrategyResponse(BaseModel):
    id: str
    created_at: str
    updated_at: str
    version: int
    asset: Dict[str, Any]
    user_input: Dict[str, str]
    analysis: Dict[str, Any]


# Routes
@router.get("/users/list")
def list_strategy_users(x_api_key: str = Header(...)):
    """List all users with strategies"""
    users = storage.list_users()
    return {"users": users}


@router.get("/users/{username}/strategies")
def list_user_strategies(username: str, x_api_key: str = Header(...)):
    """List all strategies for a user"""
    strategies = storage.list_strategies(username)
    return {"strategies": strategies}


@router.get("/users/{username}/strategies/{strategy_id}", response_model=StrategyResponse)
def get_strategy(username: str, strategy_id: str, x_api_key: str = Header(...)):
    """Get full strategy"""
    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.put("/users/{username}/strategies/{strategy_id}", response_model=StrategyResponse)
def update_strategy(username: str, strategy_id: str, strategy: Dict[str, Any], x_api_key: str = Header(...)):
    """Update strategy"""
    existing = storage.get_strategy(username, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy.get("id") != strategy_id:
        raise HTTPException(status_code=400, detail="Strategy ID mismatch")
    
    saved_id = storage.save_strategy(username, strategy)
    return storage.get_strategy(username, saved_id)
