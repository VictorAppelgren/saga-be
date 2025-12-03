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
def list_strategy_users():
    """List all users with strategies"""
    users = storage.list_users()
    return {"users": users}


@router.get("/users/{username}/strategies")
def list_user_strategies(username: str):
    """List all strategies for a user"""
    strategies = storage.list_strategies(username)
    return {"strategies": strategies}


@router.get("/users/{username}/strategies/{strategy_id}", response_model=StrategyResponse)
def get_strategy(username: str, strategy_id: str):
    """Get full strategy"""
    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.put("/users/{username}/strategies/{strategy_id}", response_model=StrategyResponse)
def update_strategy(username: str, strategy_id: str, strategy: Dict[str, Any]):
    """Update strategy"""
    existing = storage.get_strategy(username, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy.get("id") != strategy_id:
        raise HTTPException(status_code=400, detail="Strategy ID mismatch")
    
    saved_id = storage.save_strategy(username, strategy)
    return storage.get_strategy(username, saved_id)


@router.post("/users/{username}/strategies/{strategy_id}/topics")
def save_strategy_topics(username: str, strategy_id: str, topics: Dict[str, Any]):
    """Save topic mapping for strategy"""
    success = storage.save_topics(username, strategy_id, topics)
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"success": True, "topics": topics}


@router.get("/users/{username}/strategies/{strategy_id}/topics")
def get_strategy_topics(username: str, strategy_id: str):
    """Get topic mapping for strategy"""
    topics = storage.get_topics(username, strategy_id)
    if topics is None:
        raise HTTPException(status_code=404, detail="Strategy not found or no topics mapped")
    return topics


@router.post("/users/{username}/strategies/{strategy_id}/analysis")
def save_strategy_analysis(username: str, strategy_id: str, analysis: Dict[str, Any]):
    """Save analysis results (updates latest + appends to history)"""
    success = storage.save_analysis(username, strategy_id, analysis)
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"success": True, "analyzed_at": analysis.get("analyzed_at")}


@router.get("/users/{username}/strategies/{strategy_id}/analysis")
def get_latest_analysis(username: str, strategy_id: str):
    """Get latest analysis for strategy"""
    analysis = storage.get_latest_analysis(username, strategy_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Strategy not found or no analysis available")
    return analysis


@router.post("/users/{username}/strategies/{strategy_id}/question")
def save_dashboard_question(username: str, strategy_id: str, question: Dict[str, str]):
    """Save dashboard question for strategy"""
    success = storage.save_dashboard_question(username, strategy_id, question.get("question", ""))
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"success": True, "question": question.get("question")}
