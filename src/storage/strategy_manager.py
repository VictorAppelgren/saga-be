"""Strategy Storage Manager - Simple file-based storage"""
import os
import json
import random
import string
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime


class StrategyStorageManager:
    """Manages file-based strategy storage in users/"""
    
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
                        "has_analysis": strategy.get("latest_analysis", {}).get("analyzed_at") is not None,
                        "last_analyzed_at": strategy.get("latest_analysis", {}).get("analyzed_at"),
                        "is_default": strategy.get("is_default", False)
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
        """Save strategy (archives old version). If is_default=True, copies to all users."""
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
        
        # If this is a default strategy, copy to all other users
        if strategy.get("is_default", False):
            all_users = self.list_users()
            for other_user in all_users:
                if other_user != username:
                    other_user_dir = self.users_dir / other_user
                    other_user_dir.mkdir(parents=True, exist_ok=True)
                    other_strategy_path = other_user_dir / f"{strategy_id}.json"
                    
                    # Copy the strategy
                    strategy_copy = strategy.copy()
                    strategy_copy["updated_at"] = datetime.now().isoformat()
                    
                    with open(other_strategy_path, 'w') as f:
                        json.dump(strategy_copy, f, indent=2)
        
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
        
        # If this is an owner copy of a default strategy, propagate analysis to all other users' copies
        if strategy.get("is_default", False) and strategy.get("owner_username") == username:
            all_users = self.list_users()
            for other_user in all_users:
                if other_user == username:
                    continue
                other_path = self.users_dir / other_user / f"{strategy_id}.json"
                if not other_path.exists():
                    continue
                try:
                    with open(other_path, 'r') as f:
                        other_strategy = json.load(f)
                except Exception:
                    continue

                other_strategy["latest_analysis"] = analysis
                if "analysis_history" not in other_strategy:
                    other_strategy["analysis_history"] = []
                other_strategy["analysis_history"].append(analysis)
                other_strategy["updated_at"] = strategy["updated_at"]

                with open(other_path, 'w') as f:
                    json.dump(other_strategy, f, indent=2)

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
    
    def delete_strategy_from_all_users(self, strategy_id: str, except_username: str) -> None:
        """Delete a strategy from all users except the specified one"""
        all_users = self.list_users()
        for other_user in all_users:
            if other_user != except_username:
                other_user_dir = self.users_dir / other_user
                other_strategy_path = other_user_dir / f"{strategy_id}.json"
                if other_strategy_path.exists():
                    other_strategy_path.unlink()  # Delete the file
    
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
        
        # Ensure is_default is set (default to False for user-created strategies)
        if "is_default" not in strategy_data:
            strategy_data["is_default"] = False
        
        # Ensure owner is recorded (used to avoid re-analyzing default copies)
        if "owner_username" not in strategy_data:
            strategy_data["owner_username"] = username
        
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

    def get_findings(self, username: str, strategy_id: str, mode: str) -> List[Dict]:
        """Get current exploration findings (risks or opportunities) for strategy.

        Args:
            username: User who owns the strategy
            strategy_id: Strategy ID
            mode: "risk" or "opportunity"

        Returns:
            List of findings (max 3), empty list if none
        """
        strategy = self.get_strategy(username, strategy_id)
        if not strategy:
            return []

        # Get from exploration_findings section
        findings = strategy.get("exploration_findings", {})
        key = "risks" if mode == "risk" else "opportunities"
        return findings.get(key, [])

    def _generate_finding_id(self, mode: str, existing_ids: Set[str]) -> str:
        """Generate a unique finding ID.

        Format: {prefix}_{9 chars}
        - Risk: R_ABC123XYZ
        - Opportunity: O_ABC123XYZ
        """
        prefix = "R" if mode == "risk" else "O"
        charset = string.ascii_uppercase + string.digits

        for _ in range(100):  # Max attempts
            suffix = ''.join(random.choices(charset, k=9))
            new_id = f"{prefix}_{suffix}"
            if new_id not in existing_ids:
                return new_id

        # Fallback with timestamp
        import time
        return f"{prefix}_{int(time.time())}"

    def save_finding(self, username: str, strategy_id: str, mode: str, finding: Dict, replaces: Optional[int] = None) -> bool:
        """Save an exploration finding to strategy.

        Args:
            username: User who owns the strategy
            strategy_id: Strategy ID
            mode: "risk" or "opportunity"
            finding: The finding dict (headline, rationale, flow_path, evidence, confidence)
            replaces: If None, add new (max 3). If 1/2/3, replace that slot.

        Returns:
            True if saved successfully
        """
        strategy_path = self.users_dir / username / f"{strategy_id}.json"
        if not strategy_path.exists():
            return False

        with open(strategy_path, 'r') as f:
            strategy = json.load(f)

        # Initialize exploration_findings if needed
        if "exploration_findings" not in strategy:
            strategy["exploration_findings"] = {"risks": [], "opportunities": []}

        key = "risks" if mode == "risk" else "opportunities"
        if key not in strategy["exploration_findings"]:
            strategy["exploration_findings"][key] = []

        findings_list = strategy["exploration_findings"][key]

        # Collect existing IDs to avoid collisions
        existing_ids = {f.get("id") for f in findings_list if f.get("id")}

        # Generate unique finding ID if not provided
        if not finding.get("id"):
            finding["id"] = self._generate_finding_id(mode, existing_ids)

        # Add timestamp and strategy reference
        finding["added_at"] = datetime.now().isoformat()
        finding["strategy_id"] = strategy_id
        finding["username"] = username

        if replaces is not None:
            # Replace existing slot (1-indexed)
            idx = replaces - 1
            if 0 <= idx < len(findings_list):
                findings_list[idx] = finding
            else:
                # Slot doesn't exist, append instead
                findings_list.append(finding)
        else:
            # Add new - max 3
            if len(findings_list) >= 3:
                return False  # Full, need to specify which to replace
            findings_list.append(finding)

        strategy["exploration_findings"][key] = findings_list
        strategy["updated_at"] = datetime.now().isoformat()

        with open(strategy_path, 'w') as f:
            json.dump(strategy, f, indent=2)

        return True

    def get_finding_by_id(self, finding_id: str) -> Optional[Dict]:
        """Find a finding by its unique ID across all strategies.

        Args:
            finding_id: Finding ID (R_XXXXXXXXX or O_XXXXXXXXX)

        Returns:
            Finding dict with strategy context, or None if not found
        """
        if not finding_id or len(finding_id) != 11:
            return None

        # Determine mode from prefix
        if finding_id.startswith("R_"):
            mode = "risk"
        elif finding_id.startswith("O_"):
            mode = "opportunity"
        else:
            return None

        key = "risks" if mode == "risk" else "opportunities"

        # Search all users and strategies
        for user_dir in self.users_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            for strategy_file in user_dir.glob("strategy_*.json"):
                try:
                    with open(strategy_file, 'r') as f:
                        strategy = json.load(f)

                    findings = strategy.get("exploration_findings", {}).get(key, [])
                    for finding in findings:
                        if finding.get("id") == finding_id:
                            # Add context
                            finding["mode"] = mode
                            finding["username"] = user_dir.name
                            finding["strategy_id"] = strategy.get("id")
                            finding["strategy_asset"] = strategy.get("asset", {}).get("primary", "")
                            return finding

                except (json.JSONDecodeError, IOError):
                    continue

        return None
