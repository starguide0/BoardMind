"""LLM service using ollama AsyncClient."""

from __future__ import annotations
import ollama
from config import OLLAMA_HOST, TEXT_MODEL, VISION_MODEL


class LLMService:
    def __init__(self):
        self.client = ollama.AsyncClient(host=OLLAMA_HOST)

    async def chat(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
        model: str = TEXT_MODEL,
    ) -> str:
        """Generate a text response."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat(model=model, messages=messages)
            return response["message"]["content"]
        except Exception as e:
            print(f"[LLM] Error: {e}")
            return f"Error communicating with LLM: {e}"

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Analyze an image using a vision model."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": prompt,
            "images": [image_bytes],
        })

        try:
            response = await self.client.chat(
                model=VISION_MODEL,
                messages=messages,
            )
            return response["message"]["content"]
        except Exception as e:
            print(f"[LLM Vision] Error: {e}")
            return f"Error analyzing image: {e}"

    async def identify_game(self, image_bytes: bytes) -> dict:
        """Identify a board game from an image. Returns game name, confidence, and suggested roles."""
        prompt = (
            "Look at this board game image. Identify the board game being played.\n"
            "Respond in this exact format (nothing else):\n"
            "GAME: <game name>\n"
            "CONFIDENCE: <high/medium/low>\n"
            "DESCRIPTION: <one sentence about the game>\n"
            "SUGGESTED_ROLES: <comma separated list from: dm, player, referee, observer>\n"
            "\n"
            "If you cannot identify the game, respond with:\n"
            "GAME: unknown\n"
            "CONFIDENCE: low\n"
            "DESCRIPTION: Could not identify the board game.\n"
            "SUGGESTED_ROLES: observer"
        )

        text = await self.analyze_image(image_bytes, prompt)
        return self._parse_game_identification(text)

    def _parse_game_identification(self, text: str) -> dict:
        """Parse structured game identification response."""
        result = {
            "game_name": "unknown",
            "confidence": "low",
            "description": "",
            "suggested_roles": ["observer"],
        }

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("GAME:"):
                result["game_name"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("CONFIDENCE:"):
                result["confidence"] = line.split(":", 1)[1].strip().lower()
            elif line.upper().startswith("DESCRIPTION:"):
                result["description"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("SUGGESTED_ROLES:"):
                roles_str = line.split(":", 1)[1].strip()
                result["suggested_roles"] = [r.strip() for r in roles_str.split(",")]

        return result

    def build_system_prompt(self, game_name: str, role: str) -> str:
        """Build a role-specific system prompt for the AI."""
        base = (
            f"You are an AI assistant for the board game '{game_name}'. "
            "You have deep knowledge of this game's rules, strategies, and common situations. "
            "Always respond concisely and helpfully. Use Korean by default unless the user speaks another language.\n\n"
        )

        role_prompts = {
            "dm": (
                "You are the Dungeon Master / Game Master. Your responsibilities:\n"
                "- Narrate the game progress in an engaging way\n"
                "- Announce turns and significant events\n"
                "- Explain rules when players seem confused\n"
                "- Keep the game flowing and fun\n"
                "- Proactively comment on interesting board states\n"
            ),
            "player": (
                "You are a player/advisor. Your responsibilities:\n"
                "- Analyze the current board state when asked\n"
                "- Suggest optimal moves and strategies\n"
                "- Explain your reasoning\n"
                "- Respond to questions about game strategy\n"
            ),
            "referee": (
                "You are the referee/judge. Your responsibilities:\n"
                "- Monitor for rule violations\n"
                "- Clarify rules when asked\n"
                "- Validate moves and game states\n"
                "- Remain neutral and factual\n"
            ),
            "observer": (
                "You are a casual observer/commentator. Your responsibilities:\n"
                "- Provide light commentary on the game\n"
                "- Answer questions when asked\n"
                "- Stay mostly quiet unless addressed\n"
            ),
        }

        return base + role_prompts.get(role, role_prompts["observer"])
