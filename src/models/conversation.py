"""Conversation models for chat state management."""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    CONTEXT = "context"    # Hidden: initial context build
    SEARCH = "search"      # Hidden: search results


class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime


class Conversation(BaseModel):
    id: str                              # e.g., "2025-01-15_fed_policy"
    username: str
    topic_id: Optional[str] = None
    strategy_id: Optional[str] = None
    date: date
    messages: List[Message] = []
    created_at: datetime

    def get_visible_messages(self, limit: int = 10) -> List[dict]:
        """Get last N user + assistant messages for frontend."""
        visible = [
            {
                "role": m.role.value,
                "content": m.content,
                "timestamp": m.timestamp.isoformat()
            }
            for m in self.messages
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
        ]
        return visible[-limit:]

    def get_llm_messages(self) -> List[dict]:
        """Get ALL messages for LLM (including hidden context/search)."""
        messages = []
        for m in self.messages:
            if m.role == MessageRole.CONTEXT:
                messages.append({"role": "system", "content": m.content})
            elif m.role == MessageRole.SEARCH:
                # Include search results as user context
                messages.append({"role": "user", "content": m.content})
            elif m.role == MessageRole.USER:
                messages.append({"role": "user", "content": m.content})
            elif m.role == MessageRole.ASSISTANT:
                messages.append({"role": "assistant", "content": m.content})
        return messages
