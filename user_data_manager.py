"""
Simple file-based storage for user strategies.
Fail-fast, no caching, atomic writes.
"""

import os
import json
from typing import List, Dict, Optional
from datetime import datetime


USERS_DIR = os.path.join(os.path.dirname(__file__), "users")


def _ensure_user_dirs(username: str) -> None:
    """Create user directory and archive subdirectory if needed."""
    user_dir = os.path.join(USERS_DIR, username)
    archive_dir = os.path.join(user_dir, "archive")
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)


def _get_next_strategy_id(username: str) -> str:
    """Get next available strategy ID for user."""
    user_dir = os.path.join(USERS_DIR, username)
    if not os.path.exists(user_dir):
        return "strategy_001"
    
    existing = [f for f in os.listdir(user_dir) if f.startswith("strategy_") and f.endswith(".json")]
    if not existing:
        return "strategy_001"
    
    # Extract numbers from strategy_XXX.json
    numbers = []
    for f in existing:
        try:
            num = int(f.replace("strategy_", "").replace(".json", ""))
            numbers.append(num)
        except ValueError:
            continue
    
    next_num = max(numbers) + 1 if numbers else 1
    return f"strategy_{next_num:03d}"


def _archive_strategy(username: str, strategy: Dict) -> str:
    """Move strategy to archive with timestamp. Returns archived filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    strategy_id = strategy["id"]
    archived_name = f"{strategy_id}_{timestamp}.json"
    
    archive_dir = os.path.join(USERS_DIR, username, "archive")
    archive_path = os.path.join(archive_dir, archived_name)
    
    with open(archive_path, 'w') as f:
        json.dump(strategy, f, indent=2)
    
    return archived_name


def save_strategy(username: str, strategy: Dict) -> str:
    """
    Save strategy to file. If strategy exists, archive old version first.
    Returns strategy_id.
    """
    _ensure_user_dirs(username)
    
    strategy_id = strategy["id"]
    user_dir = os.path.join(USERS_DIR, username)
    strategy_path = os.path.join(user_dir, f"{strategy_id}.json")
    
    # Archive existing version if present
    if os.path.exists(strategy_path):
        with open(strategy_path, 'r') as f:
            old_strategy = json.load(f)
        _archive_strategy(username, old_strategy)
    
    # Atomic write: write to temp, then rename
    temp_path = strategy_path + ".tmp"
    with open(temp_path, 'w') as f:
        json.dump(strategy, f, indent=2)
    
    os.rename(temp_path, strategy_path)
    
    return strategy_id


def load_strategy(username: str, strategy_id: str) -> Dict:
    """Load strategy by ID. Raises FileNotFoundError if not found."""
    user_dir = os.path.join(USERS_DIR, username)
    strategy_path = os.path.join(user_dir, f"{strategy_id}.json")
    
    if not os.path.exists(strategy_path):
        raise FileNotFoundError(f"Strategy {strategy_id} not found for user {username}")
    
    with open(strategy_path, 'r') as f:
        return json.load(f)


def list_strategies(username: str) -> List[Dict]:
    """
    List all active strategies for user (summary only).
    Returns empty list if no strategies exist.
    """
    user_dir = os.path.join(USERS_DIR, username)
    if not os.path.exists(user_dir):
        return []
    
    strategies = []
    for filename in os.listdir(user_dir):
        if filename.startswith("strategy_") and filename.endswith(".json"):
            filepath = os.path.join(user_dir, filename)
            with open(filepath, 'r') as f:
                strategy = json.load(f)
                # Return summary only
                strategies.append({
                    "id": strategy["id"],
                    "asset": strategy["asset"]["primary"],
                    "target": strategy["user_input"]["target"],
                    "updated_at": strategy["updated_at"],
                    "has_analysis": strategy["analysis"]["generated_at"] is not None
                })
    
    # Sort by updated_at descending
    strategies.sort(key=lambda x: x["updated_at"], reverse=True)
    return strategies


def create_strategy(
    username: str,
    asset_primary: str,
    strategy_text: str,
    position_text: str,
    target: str
) -> Dict:
    """
    Create new strategy for user.
    Returns complete strategy object.
    """
    _ensure_user_dirs(username)
    
    strategy_id = _get_next_strategy_id(username)
    now = datetime.now().isoformat()
    
    strategy = {
        "id": strategy_id,
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "asset": {
            "primary": asset_primary,
            "related": []
        },
        "user_input": {
            "strategy_text": strategy_text,
            "position_text": position_text,
            "target": target
        },
        "analysis": {
            "generated_at": None,
            "fundamental": "",
            "current": "",
            "risks": "",
            "drivers": "",
            "supporting_evidence": [],
            "contradicting_evidence": []
        }
    }
    
    save_strategy(username, strategy)
    return strategy


def update_strategy(
    username: str,
    strategy_id: str,
    strategy_text: Optional[str] = None,
    position_text: Optional[str] = None,
    target: Optional[str] = None
) -> Dict:
    """
    Update existing strategy. Archives old version.
    Only updates provided fields.
    Returns updated strategy and archived filename.
    """
    # Load existing
    strategy = load_strategy(username, strategy_id)
    
    # Update fields if provided
    if strategy_text is not None:
        strategy["user_input"]["strategy_text"] = strategy_text
    if position_text is not None:
        strategy["user_input"]["position_text"] = position_text
    if target is not None:
        strategy["user_input"]["target"] = target
    
    # Update metadata
    strategy["updated_at"] = datetime.now().isoformat()
    strategy["version"] = strategy.get("version", 1) + 1
    
    # Save (will auto-archive old version)
    save_strategy(username, strategy)
    
    return strategy


def delete_strategy(username: str, strategy_id: str) -> str:
    """
    Delete strategy (move to archive).
    Returns archived filename.
    """
    # Load and archive
    strategy = load_strategy(username, strategy_id)
    archived_name = _archive_strategy(username, strategy)
    
    # Remove active file
    user_dir = os.path.join(USERS_DIR, username)
    strategy_path = os.path.join(user_dir, f"{strategy_id}.json")
    os.remove(strategy_path)
    
    return archived_name
