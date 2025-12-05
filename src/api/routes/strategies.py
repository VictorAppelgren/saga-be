"""Strategy API Routes"""
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import requests

from src.storage.strategy_manager import StrategyStorageManager
from src.storage.user_manager import UserManager

# Graph API URL for triggering analysis
GRAPH_API_URL = os.getenv("GRAPH_API_URL", "http://localhost:8001")

router = APIRouter(prefix="/api", tags=["strategies"])
storage = StrategyStorageManager()
user_manager = UserManager()


# Helper function to trigger analysis
def trigger_strategy_analysis(username: str, strategy_id: str):
    """Trigger strategy analysis in background (non-blocking)"""
    try:
        requests.post(
            f"{GRAPH_API_URL}/trigger/strategy-analysis",
            json={"username": username, "strategy_id": strategy_id},
            timeout=2
        )
    except Exception as e:
        print(f"⚠️  Failed to trigger analysis for {username}/{strategy_id}: {e}")


# Models
class StrategyListItem(BaseModel):
    id: str
    asset: str
    target: str
    updated_at: str
    has_analysis: bool
    last_analyzed_at: Optional[str] = None
    is_default: bool = False


class StrategyResponse(BaseModel):
    id: str
    created_at: str
    updated_at: str
    version: int
    asset: Dict[str, Any]
    user_input: Dict[str, str]
    latest_analysis: Optional[Dict[str, Any]] = None
    analysis_history: Optional[List[Dict[str, Any]]] = None
    dashboard_question: Optional[str] = None


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


@router.post("/users/{username}/strategies", response_model=StrategyResponse)
def create_strategy(username: str, strategy: Dict[str, Any], background_tasks: BackgroundTasks):
    """Create new strategy"""
    strategy_data = storage.create_strategy(username, strategy)
    
    # Trigger analysis in background
    background_tasks.add_task(trigger_strategy_analysis, username, strategy_data["id"])
    
    return strategy_data


@router.get("/users/{username}/strategies/{strategy_id}", response_model=StrategyResponse)
def get_strategy(username: str, strategy_id: str):
    """Get full strategy"""
    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.put("/users/{username}/strategies/{strategy_id}", response_model=StrategyResponse)
def update_strategy(username: str, strategy_id: str, updates: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Update strategy user_input fields ONLY.
    
    SECURITY: This endpoint ONLY allows updating user-editable fields to prevent
    accidental overwrites of system-generated data (analysis, dashboard_question, etc.)
    
    Allowed updates:
    - user_input.strategy_text
    - user_input.position_text  
    - user_input.target
    """
    existing = storage.get_strategy(username, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # PREVENT editing default strategies
    if existing.get("is_default", False):
        raise HTTPException(status_code=403, detail="Cannot edit default strategies")
    
    # WHITELIST: Only allow updating specific user_input fields
    ALLOWED_FIELDS = {"strategy_text", "position_text", "target"}
    
    # Validate that updates only contain allowed fields
    invalid_fields = set(updates.keys()) - ALLOWED_FIELDS
    if invalid_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot update fields: {invalid_fields}. Use dedicated endpoints for analysis, topics, or questions."
        )
    
    # Update only user_input fields
    if "user_input" not in existing:
        existing["user_input"] = {}
    
    for field in ALLOWED_FIELDS:
        if field in updates:
            existing["user_input"][field] = updates[field]
    
    existing["updated_at"] = datetime.now().isoformat()
    
    saved_id = storage.save_strategy(username, existing)
    
    # Trigger analysis in background
    background_tasks.add_task(trigger_strategy_analysis, username, saved_id)
    
    return storage.get_strategy(username, saved_id)


@router.delete("/users/{username}/strategies/{strategy_id}")
def delete_strategy(username: str, strategy_id: str):
    """Delete strategy (moves to archive)"""
    # Check if strategy exists and is not default
    existing = storage.get_strategy(username, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # PREVENT deleting default strategies
    if existing.get("is_default", False):
        raise HTTPException(status_code=403, detail="Cannot delete default strategies")
    
    success = storage.delete_strategy(username, strategy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"ok": True}


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


@router.get("/users/{username}/strategies/{strategy_id}/question")
def get_dashboard_question(username: str, strategy_id: str):
    """Get dashboard question for strategy"""
    question = storage.get_dashboard_question(username, strategy_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Strategy not found or no question available")
    return {"question": question}


@router.get("/users/{username}/strategies/{strategy_id}/analysis/history")
def get_analysis_history(username: str, strategy_id: str):
    """Get all analysis history for strategy"""
    history = storage.get_analysis_history(username, strategy_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"history": history, "count": len(history)}


@router.post("/users/{username}/strategies/{strategy_id}/set-default/{is_default}")
def set_strategy_default(username: str, strategy_id: str, is_default: bool):
    """Toggle is_default flag (Admin only). When set to true, copies to all users."""
    # Only admins can set default strategies
    user = user_manager.get_user_by_username(username)
    if not user or not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Only admins can set default strategies")
    
    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Update the flag
    strategy["is_default"] = is_default
    
    # Save (will auto-copy to all users if is_default=True)
    storage.save_strategy(username, strategy)
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "is_default": is_default,
        "message": f"Strategy {'is now a default example' if is_default else 'is no longer default'}"
    }
