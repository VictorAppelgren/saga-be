"""Strategy API Routes"""
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import requests

from src.storage.strategy_manager import StrategyStorageManager
from src.storage.user_manager import UserManager

# Stats tracking helper (same as main.py)
from datetime import date as date_helper
from pathlib import Path
import json as json_helper

def track_event(event_type: str, message: str = None):
    """Track a stat event (sync helper)."""
    try:
        today = date_helper.today().isoformat()
        stats_dir = Path("stats/stats")
        stats_dir.mkdir(parents=True, exist_ok=True)
        stats_file = stats_dir / f"stats_{today}.json"
        if stats_file.exists():
            stats_data = json_helper.loads(stats_file.read_text())
        else:
            stats_data = {"date": today, "events": {}}
        stats_data["events"][event_type] = stats_data["events"].get(event_type, 0) + 1
        stats_file.write_text(json_helper.dumps(stats_data, indent=2))
    except Exception:
        pass  # Non-blocking

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
    is_default: bool = False
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

    # Track strategy creation
    track_event("strategy_created", username)

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


@router.get("/users/{username}/strategies/{strategy_id}/findings/{mode}")
def get_strategy_findings(username: str, strategy_id: str, mode: str):
    """Get current exploration findings (risks or opportunities) for strategy.

    Args:
        mode: "risk" or "opportunity"

    Returns:
        List of findings (max 3)
    """
    if mode not in ("risk", "opportunity"):
        raise HTTPException(status_code=400, detail="mode must be 'risk' or 'opportunity'")

    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    findings = storage.get_findings(username, strategy_id, mode)
    return {"findings": findings, "count": len(findings), "mode": mode}


@router.post("/users/{username}/strategies/{strategy_id}/findings/{mode}")
def add_strategy_finding(username: str, strategy_id: str, mode: str, finding: Dict[str, Any]):
    """Add or replace an exploration finding.

    Args:
        mode: "risk" or "opportunity"
        finding: Dict with keys: headline, rationale, flow_path, evidence, confidence
                 Optional: replaces (int 1-3) to replace existing slot

    Returns:
        Success status
    """
    if mode not in ("risk", "opportunity"):
        raise HTTPException(status_code=400, detail="mode must be 'risk' or 'opportunity'")

    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Extract replaces if provided
    replaces = finding.pop("replaces", None)

    success = storage.save_finding(username, strategy_id, mode, finding, replaces)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to save finding. List may be full (max 3) - specify 'replaces' to replace an existing slot."
        )

    return {"success": True, "mode": mode, "replaces": replaces}


class ImproveStrategyTextRequest(BaseModel):
    """Request body for improving strategy text"""
    current_text: str  # The strategy_text to improve
    asset: str  # Primary asset for context
    position_text: Optional[str] = None  # Optional position/outlook text


@router.post("/users/{username}/strategies/{strategy_id}/improve-text")
def improve_strategy_text(username: str, strategy_id: str, request: ImproveStrategyTextRequest):
    """
    Improve the user's strategy thesis text using AI.

    Proxies to graph-functions /strategy/improve-text endpoint.
    Returns an enhanced version while preserving user's voice and core ideas.

    This embodies Saga's philosophy: AI AMPLIFIES human judgment, doesn't replace it.
    """
    # Verify strategy exists
    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        # Proxy to graph-functions
        response = requests.post(
            f"{GRAPH_API_URL}/strategy/improve-text",
            json={
                "username": username,
                "strategy_id": strategy_id,
                "current_text": request.current_text,
                "asset": request.asset,
                "position_text": request.position_text,
            },
            timeout=60  # LLM calls can take a moment
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Graph API error: {response.text}"
            )

        return response.json()

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request timed out - please try again")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach graph-functions: {str(e)}")


@router.post("/users/{username}/strategies/{strategy_id}/set-default/{is_default}")
def set_strategy_default(username: str, strategy_id: str, is_default: bool):
    """Toggle is_default flag (Admin only). When set to true, copies to all users. When false, removes from all users."""
    # Only admins can set default strategies
    user = user_manager.get_user(username)
    if not user or not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Only admins can set default strategies")
    
    strategy = storage.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Update the flag
    strategy["is_default"] = is_default
    
    if is_default:
        # Save (will auto-copy to all users)
        storage.save_strategy(username, strategy)
        message = "Strategy is now a default example and copied to all users"
    else:
        # Save locally first
        storage.save_strategy(username, strategy)
        # Delete from all other users
        storage.delete_strategy_from_all_users(strategy_id, username)
        message = "Strategy is no longer default and removed from all users"
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "is_default": is_default,
        "message": message
    }
