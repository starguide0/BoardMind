"""WebSocket message models and parser."""

from __future__ import annotations
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel


# --- Client → Server messages ---

class SessionStartMsg(BaseModel):
    type: Literal["session.start"] = "session.start"

class SessionEndMsg(BaseModel):
    type: Literal["session.end"] = "session.end"

class RoleSelectMsg(BaseModel):
    type: Literal["role.select"] = "role.select"
    role: str  # dm | player | referee | observer

class FrameCaptureMsg(BaseModel):
    type: Literal["frame.capture"] = "frame.capture"
    image: str  # base64 encoded JPEG

class VoiceInputMsg(BaseModel):
    type: Literal["voice.input"] = "voice.input"
    text: str
    lang: str = "ko"

class ChatInputMsg(BaseModel):
    type: Literal["chat.input"] = "chat.input"
    text: str

class PingMsg(BaseModel):
    type: Literal["ping"] = "ping"


ClientMessage = Union[
    SessionStartMsg, SessionEndMsg, RoleSelectMsg,
    FrameCaptureMsg, VoiceInputMsg, ChatInputMsg, PingMsg,
]

_CLIENT_MSG_MAP: dict[str, type[BaseModel]] = {
    "session.start": SessionStartMsg,
    "session.end": SessionEndMsg,
    "role.select": RoleSelectMsg,
    "frame.capture": FrameCaptureMsg,
    "voice.input": VoiceInputMsg,
    "chat.input": ChatInputMsg,
    "ping": PingMsg,
}


def parse_client_message(data: dict[str, Any]) -> ClientMessage:
    """Parse a raw dict into the appropriate client message model."""
    msg_type = data.get("type")
    model = _CLIENT_MSG_MAP.get(msg_type)
    if model is None:
        raise ValueError(f"Unknown message type: {msg_type}")
    return model.model_validate(data)


# --- Server → Client messages ---

def server_msg(type: str, **kwargs) -> dict[str, Any]:
    """Helper to build server messages."""
    return {"type": type, **kwargs}

def session_created(session_id: str) -> dict:
    return server_msg("session.created", session_id=session_id)

def game_identified(game_name: str, confidence: str, suggested_roles: list[str], description: str = "") -> dict:
    return server_msg("game.identified", game_name=game_name, confidence=confidence,
                      suggested_roles=suggested_roles, description=description)

def role_confirmed(role: str, game_name: str) -> dict:
    return server_msg("role.confirmed", role=role, game_name=game_name)

def analysis_result(content: str, move_detected: bool = False, suggestion: str = "") -> dict:
    return server_msg("analysis.result", content=content,
                      move_detected=move_detected, suggestion=suggestion)

def ai_speak(text: str, lang: str = "ko", priority: str = "normal") -> dict:
    return server_msg("ai.speak", text=text, lang=lang, priority=priority)

def turn_alert(player: str, turn_number: int) -> dict:
    return server_msg("turn.alert", player=player, turn_number=turn_number)

def timer_event(event: str, remaining: Optional[int] = None) -> dict:
    return server_msg("timer.event", event=event, remaining=remaining)

def narration(text: str) -> dict:
    return server_msg("narration", text=text)

def error_msg(message: str, code: str = "unknown") -> dict:
    return server_msg("error", message=message, code=code)

def pong() -> dict:
    return server_msg("pong")

def session_ended(session_id: str, summary: str = "") -> dict:
    return server_msg("session.ended", session_id=session_id, summary=summary)
