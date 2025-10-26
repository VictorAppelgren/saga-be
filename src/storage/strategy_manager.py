"""Strategy Storage Manager - Simple file-based storage"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class StrategyStorageManager:
    """Manages file-based strategy storage in data/users/"""
    
    def __init__(self, users_dir: str = "users"):
        self.users_dir = Path(users_dir)
    
    def list_users(self) -> List[str]:
        """List all users"""
        if not self.users_dir.exists():
            return []
        return sorted([d.name for d in self.users_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
    
    def list_strategies(self, username: str) -> List[Dict]:
        """List all strategies for a user"""
        user_dir = self.users_dir / username
        if not user_dir.exists():
            return []
        
        strategies = []
        for file_path in user_dir.glob("strategy_*.json"):
            try:
                with open(file_path, 'r') as f:
                    strategy = json.load(f)
                    strategies.append({
                        "id": strategy["id"],
                        "asset": strategy["asset"]["primary"],
                        "target": strategy["user_input"]["target"],
                        "updated_at": strategy["updated_at"],
                        "has_analysis": strategy["analysis"]["generated_at"] is not None
                    })
            except Exception:
                continue
        
        return sorted(strategies, key=lambda x: x["updated_at"], reverse=True)
    
    def get_strategy(self, username: str, strategy_id: str) -> Optional[Dict]:
        """Load full strategy"""
        strategy_path = self.users_dir / username / f"{strategy_id}.json"
        if not strategy_path.exists():
            return None
        with open(strategy_path, 'r') as f:
            return json.load(f)
    
    def save_strategy(self, username: str, strategy: Dict) -> str:
        """Save strategy (archives old version)"""
        user_dir = self.users_dir / username
        archive_dir = user_dir / "archive"
        os.makedirs(archive_dir, exist_ok=True)
        
        strategy_id = strategy["id"]
        strategy_path = user_dir / f"{strategy_id}.json"
        
        # Archive existing
        if strategy_path.exists():
            with open(strategy_path, 'r') as f:
                old_strategy = json.load(f)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = archive_dir / f"{strategy_id}_{timestamp}.json"
            with open(archive_path, 'w') as f:
                json.dump(old_strategy, f, indent=2)
        
        # Save new
        with open(strategy_path, 'w') as f:
            json.dump(strategy, f, indent=2)
        
        return strategy_id
