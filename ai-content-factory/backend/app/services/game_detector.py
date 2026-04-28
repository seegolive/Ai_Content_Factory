"""Game detector service — infer game from video title or transcript."""

from __future__ import annotations

from loguru import logger

# Keyword mapping: game_name → list of lowercase keywords
GAME_KEYWORDS: dict[str, list[str]] = {
    "Battlefield 6": ["battlefield 6", "bf6", "battlefield vi", "battlefield"],
    "Valorant": ["valorant", "valo"],
    "Kingdom Come Deliverance II": [
        "kingdom come",
        "kcd2",
        "kcd 2",
        "kingdom come deliverance",
    ],
    "Arc Raiders": ["arc raiders", "arcraiders"],
}


class GameDetector:
    def detect_from_title(self, title: str) -> str:
        """Detect game from video title. Returns game_name or '_default'."""
        title_lower = title.lower()
        for game_name, keywords in GAME_KEYWORDS.items():
            if any(kw in title_lower for kw in keywords):
                logger.debug(f"[GameDetector] '{title}' → {game_name} (title match)")
                return game_name
        return "_default"

    def detect_from_transcript(self, transcript: str) -> str:
        """Fallback: detect from first 2000 chars of transcript."""
        sample = transcript[:2000].lower()
        scores = {
            game: sum(sample.count(kw) for kw in kws)
            for game, kws in GAME_KEYWORDS.items()
        }
        best = max(scores, key=lambda g: scores[g])
        if scores[best] > 0:
            logger.debug(f"[GameDetector] Transcript → {best} (score={scores[best]})")
            return best
        return "_default"

    async def get_game_profile(
        self,
        game_name: str,
        channel_id: str,
        db,
    ):
        """
        Load GameCropProfile from DB for the given game + channel.
        Falls back to the '_default' profile if no exact match found.
        Returns None only if no profile at all exists for channel.
        """
        from sqlalchemy import select
        from app.models.channel_config import GameCropProfile

        result = await db.execute(
            select(GameCropProfile).where(
                GameCropProfile.channel_id == channel_id,
                GameCropProfile.game_name == game_name,
                GameCropProfile.is_active.is_(True),
            )
        )
        profile = result.scalars().first()
        if profile:
            return profile

        # Fallback to _default
        result = await db.execute(
            select(GameCropProfile).where(
                GameCropProfile.channel_id == channel_id,
                GameCropProfile.game_name == "_default",
            )
        )
        return result.scalars().first()
