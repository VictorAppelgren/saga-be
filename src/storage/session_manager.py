"""
Session Manager - JSON-based session token storage with expiration

Sessions persist across server restarts. Tokens expire after 24 hours.
"""
import json
import hashlib
import time
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session tokens with JSON file persistence"""

    def __init__(self, sessions_file: str = "data/sessions.json"):
        self.sessions_file = Path(sessions_file)
        self.sessions_file.parent.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, dict] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load sessions from JSON file"""
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    # Filter out expired sessions on load
                    now = datetime.now().isoformat()
                    self._sessions = {
                        token: info for token, info in data.items()
                        if info.get("expires_at", "") > now
                    }
                    logger.info(f"Loaded {len(self._sessions)} valid sessions")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load sessions: {e}")
                self._sessions = {}
        else:
            self._sessions = {}

    def _save_sessions(self) -> None:
        """Save sessions to JSON file"""
        try:
            with open(self.sessions_file, 'w') as f:
                json.dump(self._sessions, f, indent=2)
        except IOError as e:
            logger.error(f"Could not save sessions: {e}")

    def create_session(self, username: str, ttl_hours: int = 24) -> str:
        """Create a new session token for user. Returns the token."""
        # Generate secure token
        token = hashlib.sha256(f"{username}{time.time()}{time.perf_counter()}".encode()).hexdigest()

        # Calculate expiration
        expires_at = datetime.now() + timedelta(hours=ttl_hours)

        # Store session
        self._sessions[token] = {
            "username": username,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat()
        }

        self._save_sessions()
        logger.info(f"Created session for {username}, expires {expires_at.isoformat()}")
        return token

    def validate_session(self, token: str) -> Optional[str]:
        """
        Validate a session token.
        Returns username if valid, None if invalid/expired.
        """
        if not token or token not in self._sessions:
            return None

        session = self._sessions[token]

        # Check expiration
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now() > expires_at:
            # Token expired - remove it
            del self._sessions[token]
            self._save_sessions()
            logger.info(f"Session expired for {session['username']}")
            return None

        return session["username"]

    def invalidate_session(self, token: str) -> bool:
        """Invalidate (logout) a session. Returns True if session existed."""
        if token in self._sessions:
            username = self._sessions[token]["username"]
            del self._sessions[token]
            self._save_sessions()
            logger.info(f"Invalidated session for {username}")
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count of removed sessions."""
        now = datetime.now().isoformat()
        expired = [
            token for token, info in self._sessions.items()
            if info.get("expires_at", "") <= now
        ]

        for token in expired:
            del self._sessions[token]

        if expired:
            self._save_sessions()
            logger.info(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)


# Global instance
session_manager = SessionManager()
