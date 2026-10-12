"""Conversation history manager with sliding window and /clear support."""

from collections import deque
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    """Single chat turn in conversation."""

    role: str  # "user" or "assistant"
    content: str


@dataclass
class UserSession:
    """User state holding history turns and model preference."""

    model: str
    system_prompt: str
    history: deque[ChatMessage] = field(default_factory=deque)


class ConversationManager:
    """Manages multi-turn conversation context per Telegram user.

    Enforces sliding window of last N turns and handles system prompt injection.
    """

    def __init__(
        self,
        default_model: str = "deepseek-v4.1-flash",
        default_system_prompt: str = "You are a helpful AI assistant.",
        max_turns: int = 10,
    ):
        self.default_model = default_model
        self.default_system_prompt = default_system_prompt
        self.max_turns = max_turns
        self._sessions: dict[int, UserSession] = {}

    def _get_or_create_session(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(
                model=self.default_model,
                system_prompt=self.default_system_prompt,
                history=deque(maxlen=self.max_turns * 2),  # Each turn is user + assistant
            )
        return self._sessions[user_id]

    def get_model(self, user_id: int) -> str:
        """Get currently active model for user."""
        return self._get_or_create_session(user_id).model

    def set_model(self, user_id: int, model: str) -> None:
        """Set active model preference for user."""
        session = self._get_or_create_session(user_id)
        session.model = model

    def set_system_prompt(self, user_id: int, prompt: str) -> None:
        """Override system prompt for user."""
        session = self._get_or_create_session(user_id)
        session.system_prompt = prompt

    def add_user_message(self, user_id: int, content: str) -> None:
        """Append user message to session history."""
        session = self._get_or_create_session(user_id)
        session.history.append(ChatMessage(role="user", content=content))

    def add_assistant_message(self, user_id: int, content: str) -> None:
        """Append assistant message to session history."""
        session = self._get_or_create_session(user_id)
        session.history.append(ChatMessage(role="assistant", content=content))

    def get_messages(self, user_id: int) -> list[dict[str, str]]:
        """Construct full prompt payload for OpenAI-compatible API."""
        session = self._get_or_create_session(user_id)
        messages: list[dict[str, str]] = []

        if session.system_prompt:
            messages.append({"role": "system", "content": session.system_prompt})

        for item in session.history:
            messages.append({"role": item.role, "content": item.content})

        return messages

    def clear(self, user_id: int) -> None:
        """Clear conversation history while preserving user model preference."""
        if user_id in self._sessions:
            self._sessions[user_id].history.clear()

    def get_turns_count(self, user_id: int) -> int:
        """Get number of messages currently stored in user context."""
        if user_id not in self._sessions:
            return 0
        return len(self._sessions[user_id].history)
