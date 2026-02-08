"""AI-based game management - no hardcoded rules."""

from __future__ import annotations
from models.session import GameSession
from services.llm_service import LLMService
from services.vision_service import VisionService
from models import messages as msg


class GameManager:
    def __init__(self, llm_service: LLMService, vision_service: VisionService):
        self.llm = llm_service
        self.vision = vision_service

    async def handle_frame(self, session: GameSession, base64_image: str) -> list[dict]:
        """Process a captured frame. Returns a list of server messages to send."""
        image_bytes = self.vision.decode_frame(base64_image)
        responses: list[dict] = []

        # If game not identified yet, try to identify it
        if not session.is_game_identified:
            result = await self.vision.identify_game(image_bytes)
            session.game_name = result["game_name"]
            responses.append(msg.game_identified(
                game_name=result["game_name"],
                confidence=result["confidence"],
                suggested_roles=result["suggested_roles"],
                description=result["description"],
            ))
            return responses

        # Build system prompt based on role
        system_prompt = self.llm.build_system_prompt(
            session.game_name, session.ai_role or "observer"
        )

        # Analyze board state
        analysis = await self.vision.analyze_board(
            image_bytes,
            system_prompt=system_prompt,
            last_description=session.last_board_description,
        )

        session.last_board_description = analysis["content"]
        session.add_message("assistant", analysis["content"])

        responses.append(msg.analysis_result(
            content=analysis["content"],
            move_detected=analysis["move_detected"],
        ))

        # If a move was detected and AI is DM, provide narration
        if analysis["move_detected"] and session.ai_role == "dm":
            narration_text = await self.llm.chat(
                prompt=(
                    f"A move was just made. Board state: {analysis['content']}\n"
                    "Provide a brief, engaging narration of this move (1-2 sentences)."
                ),
                system_prompt=system_prompt,
                history=session.history[-6:],
            )
            session.add_message("assistant", narration_text)
            responses.append(msg.narration(narration_text))
            responses.append(msg.ai_speak(narration_text, lang="ko"))

        return responses

    async def handle_role_select(self, session: GameSession, role: str) -> list[dict]:
        """Set the AI role for this session."""
        session.ai_role = role
        responses: list[dict] = []
        responses.append(msg.role_confirmed(role=role, game_name=session.game_name or "unknown"))

        # Generate a greeting based on role
        if session.game_name:
            system_prompt = self.llm.build_system_prompt(session.game_name, role)
            greeting = await self.llm.chat(
                prompt=(
                    f"You've just been assigned as the {role} for a game of {session.game_name}. "
                    "Introduce yourself briefly and set the mood (1-2 sentences)."
                ),
                system_prompt=system_prompt,
            )
            session.add_message("assistant", greeting)
            responses.append(msg.ai_speak(greeting, lang="ko"))

        return responses

    async def handle_chat(self, session: GameSession, text: str) -> list[dict]:
        """Handle text chat input."""
        session.add_message("user", text)

        system_prompt = self.llm.build_system_prompt(
            session.game_name or "unknown", session.ai_role or "observer"
        )

        reply = await self.llm.chat(
            prompt=text,
            system_prompt=system_prompt,
            history=session.history[-10:],
        )

        session.add_message("assistant", reply)

        return [
            msg.analysis_result(content=reply),
            msg.ai_speak(reply, lang="ko"),
        ]

    async def handle_voice(self, session: GameSession, text: str, lang: str) -> list[dict]:
        """Handle voice input (same as chat but may adjust language)."""
        return await self.handle_chat(session, text)
