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
                        "has_analysis": strategy.get("latest_analysis", {}).get("analyzed_at") is not None
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
    
    def save_topics(self, username: str, strategy_id: str, topics: Dict) -> bool:
        """Save topic mapping to strategy (simple field update)"""
        strategy_path = self.users_dir / username / f"{strategy_id}.json"
        if not strategy_path.exists():
            return False
        
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        
        strategy["topics"] = {
            "mapped_at": datetime.now().isoformat(),
            **topics
        }
        strategy["updated_at"] = datetime.now().isoformat()
        
        with open(strategy_path, 'w') as f:
            json.dump(strategy, f, indent=2)
        
        return True
    
    def get_topics(self, username: str, strategy_id: str) -> Optional[Dict]:
        """Get topic mapping from strategy"""
        strategy = self.get_strategy(username, strategy_id)
        return strategy.get("topics") if strategy else None
    
    def save_analysis(self, username: str, strategy_id: str, analysis: Dict) -> bool:
        """Save analysis results (updates latest + appends to history)"""
        strategy_path = self.users_dir / username / f"{strategy_id}.json"
        if not strategy_path.exists():
            return False
        
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        
        # Add timestamp
        analysis["analyzed_at"] = datetime.now().isoformat()
        
        # Update latest
        strategy["latest_analysis"] = analysis
        
        # Append to history
        if "analysis_history" not in strategy:
            strategy["analysis_history"] = []
        strategy["analysis_history"].append(analysis)
        
        strategy["updated_at"] = datetime.now().isoformat()
        
        with open(strategy_path, 'w') as f:
            json.dump(strategy, f, indent=2)
        
        return True
    
    def get_latest_analysis(self, username: str, strategy_id: str) -> Optional[Dict]:
        """Get latest analysis from strategy"""
        strategy = self.get_strategy(username, strategy_id)
        return strategy.get("latest_analysis") if strategy else None
    
    def save_dashboard_question(self, username: str, strategy_id: str, question: str) -> bool:
        """Save dashboard question to strategy (simple field update)"""
        strategy_path = self.users_dir / username / f"{strategy_id}.json"
        if not strategy_path.exists():
            return False
        
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        
        strategy["dashboard_question"] = question
        strategy["updated_at"] = datetime.now().isoformat()
        
        with open(strategy_path, 'w') as f:
            json.dump(strategy, f, indent=2)
        
        return True
    
    def get_dashboard_question(self, username: str, strategy_id: str) -> Optional[str]:
        """Get dashboard question from strategy"""
        strategy = self.get_strategy(username, strategy_id)
        return strategy.get("dashboard_question") if strategy else None
    
    def get_analysis_history(self, username: str, strategy_id: str) -> List[Dict]:
        """Get all analysis history from strategy"""
        strategy = self.get_strategy(username, strategy_id)
        return strategy.get("analysis_history", []) if strategy else []
    
    def create_strategy(self, username: str, strategy_data: Dict) -> Dict:
        """Create new strategy with proper initialization"""
        user_dir = self.users_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate ID if not provided
        if "id" not in strategy_data:
            strategy_data["id"] = f"strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Add timestamps
        now = datetime.now().isoformat()
        strategy_data["created_at"] = now
        strategy_data["updated_at"] = now
        strategy_data["version"] = 1
        
        # Save
        self.save_strategy(username, strategy_data)
        return strategy_data
    
    def update_strategy(self, username: str, strategy_id: str, updates: Dict) -> bool:
        """Update strategy metadata (not analysis/topics/question)"""
        strategy_path = self.users_dir / username / f"{strategy_id}.json"
        if not strategy_path.exists():
            return False
        
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        
        # Only allow updating specific fields
        allowed_fields = ["asset", "user_input", "version"]
        for field in allowed_fields:
            if field in updates:
                strategy[field] = updates[field]
        
        strategy["updated_at"] = datetime.now().isoformat()
        
        with open(strategy_path, 'w') as f:
            json.dump(strategy, f, indent=2)
        
        return True
    
    def delete_strategy(self, username: str, strategy_id: str) -> bool:
        """Delete strategy (moves to archive)"""
        strategy_path = self.users_dir / username / f"{strategy_id}.json"
        if not strategy_path.exists():
            return False
        
        # Move to archive
        user_dir = self.users_dir / username
        archive_dir = user_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"{strategy_id}_deleted_{timestamp}.json"
        
        strategy_path.rename(archive_path)
        return True
