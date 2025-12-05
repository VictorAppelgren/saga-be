"""User Manager - Simple JSON-based user authentication"""
import json
from pathlib import Path
from typing import Optional, Dict, List


class UserManager:
    """Manages user authentication and access"""
    
    def __init__(self, users_file: str = "users/users.json"):
        self.users_file = Path(users_file)
        self._users = None
    
    def _load_users(self) -> Dict:
        """Load users from JSON file"""
        if self._users is None:
            with open(self.users_file, 'r') as f:
                self._users = json.load(f)
        return self._users
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user, returns user dict or None"""
        users_data = self._load_users()
        for user in users_data["users"]:
            if user["username"] == username and user["password"] == password:
                return {
                    "username": user["username"],
                    "accessible_topics": user["accessible_topics"],
                    "is_admin": user.get("is_admin", False)
                }
        return None
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user by username (without password)"""
        users_data = self._load_users()
        for user in users_data["users"]:
            if user["username"] == username:
                return {
                    "username": user["username"],
                    "accessible_topics": user["accessible_topics"],
                    "is_admin": user.get("is_admin", False)
                }
        return None
    
    def list_users(self) -> List[str]:
        """List all usernames"""
        users_data = self._load_users()
        return [user["username"] for user in users_data["users"]]
    
    def validate_api_key(self, api_key: str, expected_key: str) -> bool:
        """Validate API key"""
        return api_key == expected_key
    
    def ensure_user_directories(self, base_path: str = "data/users"):
        """Ensure all users from users.json have directories"""
        users_data = self._load_users()
        base_dir = Path(base_path)
        base_dir.mkdir(parents=True, exist_ok=True)
        
        for user in users_data.get("users", []):
            username = user.get("username")
            if username:
                user_dir = base_dir / username
                user_dir.mkdir(parents=True, exist_ok=True)
