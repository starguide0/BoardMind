"""WebSocket message router and handler."""

from __future__ import annotations
import json
import traceback
from fastapi import WebSocket, WebSocketDisconnect
from models.messages import parse_client_message, error_msg, pong, session_created, session_ended
from services.session_manager import SessionManager
from services.game_manager import GameManager


class WebSocketHandler:
    def __init__(self, session_manager: SessionManager, game_manager: GameManager):
        self.sessions = session_manager
        self.game = game_manager
        # Map: websocket -> session_id
        self._ws_sessions: dict[WebSocket, str] = {}

    async def handle_connection(self, websocket: WebSocket):
        """Main WebSocket connection handler."""
        await websocket.accept()
        print("[WS] Client connected")

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                    message = parse_client_message(data)
                    responses = await self._route(websocket, message)
                    for resp in responses:
                        await websocket.send_json(resp)
                except (ValueError, json.JSONDecodeError) as e:
                    await websocket.send_json(error_msg(str(e), code="parse_error"))
                except Exception as e:
                    traceback.print_exc()
                    await websocket.send_json(error_msg(str(e), code="handler_error"))

        except WebSocketDisconnect:
            print("[WS] Client disconnected")
            self._cleanup(websocket)

    async def _route(self, ws: WebSocket, message) -> list[dict]:
        """Route a parsed message to the appropriate handler."""
        msg_type = message.type

        if msg_type == "ping":
            return [pong()]

        if msg_type == "session.start":
            return await self._handle_session_start(ws)

        if msg_type == "session.end":
            return await self._handle_session_end(ws)

        # All other messages require an active session
        session_id = self._ws_sessions.get(ws)
        if not session_id:
            return [error_msg("No active session. Send session.start first.", code="no_session")]

        session = self.sessions.get_session(session_id)
        if not session:
            return [error_msg("Session not found.", code="session_not_found")]

        if msg_type == "role.select":
            return await self.game.handle_role_select(session, message.role)
        elif msg_type == "frame.capture":
            return await self.game.handle_frame(session, message.image)
        elif msg_type == "chat.input":
            return await self.game.handle_chat(session, message.text)
        elif msg_type == "voice.input":
            return await self.game.handle_voice(session, message.text, message.lang)
        else:
            return [error_msg(f"Unhandled message type: {msg_type}", code="unhandled")]

    async def _handle_session_start(self, ws: WebSocket) -> list[dict]:
        """Create a new session for this connection."""
        # End existing session if any
        old_id = self._ws_sessions.get(ws)
        if old_id:
            self.sessions.end_session(old_id)

        session = self.sessions.create_session()
        self._ws_sessions[ws] = session.id
        print(f"[WS] Session created: {session.id}")
        return [session_created(session.id)]

    async def _handle_session_end(self, ws: WebSocket) -> list[dict]:
        """End the current session."""
        session_id = self._ws_sessions.pop(ws, None)
        if session_id:
            session = self.sessions.end_session(session_id)
            summary = f"Game: {session.game_name or 'N/A'}, Turns: {session.turn_number}" if session else ""
            print(f"[WS] Session ended: {session_id}")
            return [session_ended(session_id, summary=summary)]
        return [error_msg("No active session to end.", code="no_session")]

    def _cleanup(self, ws: WebSocket):
        """Clean up when a WebSocket disconnects."""
        session_id = self._ws_sessions.pop(ws, None)
        if session_id:
            self.sessions.end_session(session_id)
            print(f"[WS] Cleaned up session: {session_id}")
