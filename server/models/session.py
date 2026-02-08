"""Game session data model."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class GameSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=datetime.now)

    # Game state
    game_name: Optional[str] = None
    ai_role: Optional[str] = None  # dm | player | referee | observer
    turn_number: int = 0
    current_player: Optional[str] = None

    # Conversation history for LLM context
    history: list[dict[str, str]] = field(default_factory=list)

    # Last analyzed frame description (to detect changes)
    last_board_description: Optional[str] = None

    @property
    def is_game_identified(self) -> bool:
        return self.game_name is not None

    @property
    def is_role_set(self) -> bool:
        return self.ai_role is not None

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        # Keep history manageable
        if len(self.history) > 50:
            self.history = self.history[-40:]
