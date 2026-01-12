"""Strategy API Routes"""
import logging
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import requests

from src.storage.strategy_manager import StrategyStorageManager
from src.storage.user_manager import UserManager

logger = logging.getLogger(__name__)

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
        logger.info(f"Triggering analysis for {username}/{strategy_id}")
        response = requests.post(
            f"{GRAPH_API_URL}/trigger/strategy-analysis",
            json={"username": username, "strategy_id": strategy_id},
            timeout=2
        )
        logger.info(f"Trigger response for {username}/{strategy_id}: {response.status_code}")
        track_event("strategy_analysis_triggered", f"{username}/{strategy_id}")
    except requests.exceptions.Timeout:
        # Timeout is OK - the graph API accepted the request and is processing in background
        logger.info(f"Trigger timed out (expected) for {username}/{strategy_id} - analysis running in background")
        track_event("strategy_analysis_triggered", f"{username}/{strategy_id}")
    except Exception as e:
        logger.error(f"Failed to trigger analysis for {username}/{strategy_id}: {e}")
        track_event("strategy_analysis_trigger_failed", f"{username}/{strategy_id}")


# Valid stance values
VALID_STANCES = {"bull", "bear", "neutral", None}

# Valid position status values
VALID_POSITION_STATUSES = {"monitoring", "looking_to_enter", "in_position", None}

# Valid time horizons (swing trading to buy-and-hold, NO intraday)
VALID_TIME_HORIZONS = {"weeks", "months", "quarters", None}


# Models
class StrategyListItem(BaseModel):
    id: str
    asset: str
    target: str
    updated_at: str
    has_analysis: bool
    last_analyzed_at: Optional[str] = None
    is_default: bool = False
    stance: Optional[str] = None  # bull, bear, neutral, or None
    position_status: Optional[str] = None  # monitoring, looking_to_enter, in_position
    time_horizon: Optional[str] = None  # weeks, months, quarters


class StrategyResponse(BaseModel):
    id: str
    created_at: str
    updated_at: str
    version: int
    is_default: bool = False
    stance: Optional[str] = None  # bull, bear, neutral, or None
    position_status: Optional[str] = None  # monitoring, looking_to_enter, in_position
    time_horizon: Optional[str] = None  # weeks, months, quarters
    asset: Dict[str, Any]
    user_input: Dict[str, str]
    latest_analysis: Optional[Dict[str, Any]] = None
    analysis_history: Optional[List[Dict[str, Any]]] = None
    dashboard_question: Optional[str] = None
    exploration_findings: Optional[Dict[str, Any]] = None


class UpdateStanceRequest(BaseModel):
    """Request body for updating stance"""
    stance: Optional[str] = None  # bull, bear, neutral, or None


class UpdatePositionStatusRequest(BaseModel):
    """Request body for updating position status and time horizon"""
    position_status: Optional[str] = None  # monitoring, looking_to_enter, in_position
    time_horizon: Optional[str] = None  # weeks, months, quarters


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

    # Track strategy view
    track_event("strategy_viewed", f"{username}/{strategy_id}")

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

    # Check if user is admin
    user = user_manager.get_user(username)
    is_admin = user and user.get("is_admin", False)

    # PREVENT editing default strategies (unless admin)
    if existing.get("is_default", False) and not is_admin:
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

    # Track strategy update
    track_event("strategy_updated", f"{username}/{saved_id}")

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


@router.put("/users/{username}/strategies/{strategy_id}/stance")
def update_strategy_stance(username: str, strategy_id: str, request: UpdateStanceRequest, background_tasks: BackgroundTasks):
    """
    Update strategy stance (directional view).

    Stance values:
    - "bull": User believes asset will go UP - system validates/invalidates bull thesis
    - "bear": User believes asset will go DOWN - system validates/invalidates bear thesis
    - "neutral": Monitoring/no view - system provides balanced analysis of both sides
    - null: Not set (treated same as neutral for analysis)

    Note: Changing stance triggers re-analysis as prompts are stance-aware.
    """
    existing = storage.get_strategy(username, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Validate stance value
    if request.stance not in VALID_STANCES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stance. Must be one of: 'bull', 'bear', 'neutral', or null"
        )

    # Check if user is admin (for default strategies)
    user = user_manager.get_user(username)
    is_admin = user and user.get("is_admin", False)

    # PREVENT editing default strategies (unless admin)
    if existing.get("is_default", False) and not is_admin:
        raise HTTPException(status_code=403, detail="Cannot edit default strategies")

    # Update stance
    success = storage.update_stance(username, strategy_id, request.stance)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update stance")

    # Track stance update
    track_event("stance_updated", f"{username}/{strategy_id}:{request.stance}")

    # Trigger re-analysis since stance affects how agents interpret the strategy
    background_tasks.add_task(trigger_strategy_analysis, username, strategy_id)

    return {
        "success": True,
        "strategy_id": strategy_id,
        "stance": request.stance,
        "message": f"Stance updated to '{request.stance or 'neutral'}'. Re-analysis triggered."
    }


@router.put("/users/{username}/strategies/{strategy_id}/position-status")
def update_strategy_position_status(
    username: str,
    strategy_id: str,
    request: UpdatePositionStatusRequest,
    background_tasks: BackgroundTasks
):
    """
    Update strategy position status and time horizon.

    Position Status (lifecycle stage):
    - "monitoring": Watching the asset, no directional view yet
    - "looking_to_enter": Have a thesis, seeking confirmation before entry
    - "in_position": Currently holding, monitoring for thesis INVALIDATION
    - null: Not set (treated as monitoring)

    Time Horizon (swing trading to buy-and-hold - NO intraday):
    - "weeks": 1-4 weeks (swing trade)
    - "months": 1-6 months (position trade)
    - "quarters": 6+ months (investment)
    - null: Not specified

    Note: Changing position status triggers re-analysis as prompts adapt to lifecycle.
    """
    existing = storage.get_strategy(username, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Validate position_status value
    if request.position_status not in VALID_POSITION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid position_status. Must be one of: 'monitoring', 'looking_to_enter', 'in_position', or null"
        )

    # Validate time_horizon value
    if request.time_horizon not in VALID_TIME_HORIZONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time_horizon. Must be one of: 'weeks', 'months', 'quarters', or null"
        )

    # Check if user is admin (for default strategies)
    user = user_manager.get_user(username)
    is_admin = user and user.get("is_admin", False)

    # PREVENT editing default strategies (unless admin)
    if existing.get("is_default", False) and not is_admin:
        raise HTTPException(status_code=403, detail="Cannot edit default strategies")

    # Update position status
    success = storage.update_position_status(
        username, strategy_id, request.position_status, request.time_horizon
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update position status")

    # Track update
    track_event("position_status_updated", f"{username}/{strategy_id}:{request.position_status}")

    # Trigger re-analysis since position status affects how agents interpret the strategy
    background_tasks.add_task(trigger_strategy_analysis, username, strategy_id)

    return {
        "success": True,
        "strategy_id": strategy_id,
        "position_status": request.position_status,
        "time_horizon": request.time_horizon,
        "message": f"Position status updated to '{request.position_status or 'monitoring'}'. Re-analysis triggered."
    }


@router.get("/findings/{finding_id}")
def get_finding_by_id(finding_id: str):
    """
    Get a finding by its unique ID (searches all strategies).

    Finding IDs:
    - R_XXXXXXXXX = Risk finding
    - O_XXXXXXXXX = Opportunity finding

    Returns the finding with strategy context.
    """
    # Validate format
    if not finding_id or len(finding_id) != 11:
        raise HTTPException(status_code=400, detail="Invalid finding ID format")

    if not finding_id.startswith("R_") and not finding_id.startswith("O_"):
        raise HTTPException(status_code=400, detail="Finding ID must start with R_ or O_")

    finding = storage.get_finding_by_id(finding_id)

    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")

    return {
        "id": finding_id,
        "mode": finding.get("mode", "risk" if finding_id.startswith("R_") else "opportunity"),
        "username": finding.get("username"),
        "strategy_id": finding.get("strategy_id"),
        "strategy_asset": finding.get("strategy_asset", ""),
        "headline": finding.get("headline", ""),
        "rationale": finding.get("rationale", ""),
        "flow_path": finding.get("flow_path", ""),
        "evidence": finding.get("evidence", []),
        "confidence": finding.get("confidence", ""),
        "added_at": finding.get("added_at", ""),
        "target_topic": finding.get("target_topic", ""),
    }
