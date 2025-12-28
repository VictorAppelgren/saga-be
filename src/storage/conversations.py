"""File-based conversation storage. One JSON file per conversation per user."""
import json
from pathlib import Path
from datetime import date, datetime
from typing import Optional, List

from src.models.conversation import Conversation, Message, MessageRole

# Store under users/ to match strategy storage pattern
USERS_DIR = Path("users")


class ConversationStore:
    """Simple file-based conversation storage."""

    def __init__(self):
        USERS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_user_dir(self, username: str) -> Path:
        """Get/create user's conversations directory."""
        conv_dir = USERS_DIR / username / "conversations"
        conv_dir.mkdir(parents=True, exist_ok=True)
        return conv_dir

    def _make_id(self, topic_id: str = None, strategy_id: str = None) -> str:
        """Generate conversation ID: {date}_{context}."""
        today = date.today().isoformat()
        context = topic_id or strategy_id or "general"
        return f"{today}_{context}"

    def _get_file(self, username: str, conv_id: str) -> Path:
        return self._get_user_dir(username) / f"{conv_id}.json"

    def get(self, username: str, conv_id: str) -> Optional[Conversation]:
        """Load conversation from file."""
        file = self._get_file(username, conv_id)
        if file.exists():
            data = json.loads(file.read_text())
            return Conversation(**data)
        return None

    def get_or_create(
        self,
        username: str,
        topic_id: str = None,
        strategy_id: str = None
    ) -> tuple:
        """
        Get today's conversation or create new one.
        Returns (conversation, is_new).
        """
        conv_id = self._make_id(topic_id, strategy_id)
        existing = self.get(username, conv_id)

        if existing:
            return existing, False

        # Create new conversation for today
        new_conv = Conversation(
            id=conv_id,
            username=username,
            topic_id=topic_id,
            strategy_id=strategy_id,
            date=date.today(),
            messages=[],
            created_at=datetime.now()
        )
        return new_conv, True

    def save(self, conv: Conversation):
        """Save conversation to file."""
        file = self._get_file(conv.username, conv.id)
        file.write_text(conv.model_dump_json(indent=2))

    def list_for_user(self, username: str) -> List[str]:
        """List all conversation IDs for a user."""
        user_dir = self._get_user_dir(username)
        return [f.stem for f in user_dir.glob("*.json")]


# Global instance
conversation_store = ConversationStore()
