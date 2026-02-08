"""Vision service - base64 decoding and LLM delegation."""

from __future__ import annotations
import base64
from services.llm_service import LLMService


class VisionService:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def decode_frame(self, base64_image: str) -> bytes:
        """Decode a base64 encoded image to bytes."""
        # Strip data URL prefix if present
        if "," in base64_image:
            base64_image = base64_image.split(",", 1)[1]
        return base64.b64decode(base64_image)

    async def analyze_board(
        self,
        image_bytes: bytes,
        system_prompt: str,
        last_description: str | None = None,
    ) -> dict:
        """Analyze the board state, optionally comparing to previous state."""
        prompt_parts = ["Describe the current board game state you see in this image."]

        if last_description:
            prompt_parts.append(
                f"\nThe previous board state was: '{last_description}'\n"
                "Compare and describe what has changed. Identify any moves that were made."
            )
        else:
            prompt_parts.append(
                "This is the first look at the board. Describe the overall state."
            )

        prompt_parts.append("\nBe concise (2-3 sentences max).")

        content = await self.llm.analyze_image(
            image_bytes,
            "\n".join(prompt_parts),
            system_prompt=system_prompt,
        )

        move_detected = last_description is not None and "change" in content.lower()

        return {
            "content": content,
            "move_detected": move_detected,
        }

    async def identify_game(self, image_bytes: bytes) -> dict:
        """Delegate game identification to LLM."""
        return await self.llm.identify_game(image_bytes)
