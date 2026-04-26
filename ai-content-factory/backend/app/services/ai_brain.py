"""AI Brain service — analyzes transcripts and generates viral clip suggestions via OpenRouter."""
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.transcription import TranscriptResult

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class ClipSuggestion:
    start_time: float
    end_time: float
    viral_score: int
    titles: List[str]  # 3 A/B variants
    hook_text: str
    description: str
    hashtags: List[str]
    thumbnail_prompt: str
    reason: str


@dataclass
class AIAnalysisResult:
    clips: List[ClipSuggestion]
    processing_time: float
    model_used: str
    tokens_used: int


ANALYSIS_SYSTEM_PROMPT = """You are an expert viral content analyst specializing in short-form video clips.
Your task is to analyze a video transcript and identify the most viral-worthy segments.

Viral scoring criteria (total 100 points):
- Emotional impact (0-25): Does it evoke strong emotion? Surprise, inspiration, humor, shock?
- Information density (0-20): Is there valuable, actionable, or surprising information?
- Hook strength in first 5 seconds (0-25): Does it grab attention immediately?
- Relatability & shareability (0-15): Would people share this? Tag friends?
- Call-to-action potential (0-15): Does it drive engagement, curiosity, or follow-through?

For each clip, generate:
1. start_time and end_time (in seconds) — optimal segment, 30-90 seconds
2. viral_score (0-100)
3. titles: exactly 3 variants (clickbait-but-honest, curiosity gap, how-to format)
4. hook_text: the first sentence that grabs attention in <10 words
5. description: 2-3 sentence SEO-optimized description with keywords
6. hashtags: 10-15 relevant hashtags without the # symbol
7. thumbnail_prompt: a SDXL image prompt describing the ideal thumbnail
8. reason: 1-2 sentences explaining why this segment is viral

Return ONLY a valid JSON object with this structure:
{
  "clips": [
    {
      "start_time": 12.5,
      "end_time": 75.2,
      "viral_score": 87,
      "titles": ["Title 1", "Title 2", "Title 3"],
      "hook_text": "Nobody told you this about money",
      "description": "...",
      "hashtags": ["personalfinance", "moneytips"],
      "thumbnail_prompt": "...",
      "reason": "..."
    }
  ]
}

Identify 5-15 clips. Minimum viral_score to include: 60."""


class AIBrainService:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://ai-content-factory.app",
                "X-Title": "AI Content Factory",
            },
            timeout=120.0,
        )

    async def analyze_transcript(
        self,
        transcript: TranscriptResult,
        channel_info: Optional[dict] = None,
    ) -> AIAnalysisResult:
        """Analyze transcript and return viral clip suggestions."""
        start = time.perf_counter()

        # Build transcript text with timestamps
        segments_text = "\n".join(
            f"[{seg.start:.1f}s - {seg.end:.1f}s]: {seg.text}"
            for seg in transcript.segments
        )

        channel_context = ""
        if channel_info:
            channel_context = f"\nChannel context: {json.dumps(channel_info)}"

        user_message = f"""Analyze this video transcript and identify viral clips.

Video duration: {transcript.duration:.1f} seconds
Language: {transcript.language}
Word count: {transcript.word_count}
{channel_context}

TRANSCRIPT:
{segments_text}

Full text:
{transcript.full_text[:4000]}
"""

        response = await self._call_openrouter(
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            model=settings.OPENROUTER_MODEL,
            max_tokens=4000,
        )

        elapsed = time.perf_counter() - start

        # Parse JSON response
        clips = self._parse_clip_suggestions(response["content"])

        return AIAnalysisResult(
            clips=clips,
            processing_time=elapsed,
            model_used=response["model"],
            tokens_used=response.get("tokens_used", 0),
        )

    async def generate_titles(self, clip_info: dict) -> List[str]:
        """Generate 3 title variants for a clip."""
        response = await self._call_openrouter(
            messages=[
                {
                    "role": "user",
                    "content": f"Generate 3 viral YouTube title variants for this clip. "
                    f"Return JSON array only.\n\nClip info: {json.dumps(clip_info)}",
                }
            ],
            model=settings.OPENROUTER_FALLBACK_MODEL,
            max_tokens=300,
        )
        try:
            return json.loads(response["content"])
        except json.JSONDecodeError:
            return [clip_info.get("title", "Untitled")]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _call_openrouter(
        self,
        messages: list,
        model: str,
        max_tokens: int = 2000,
    ) -> dict:
        """Call OpenRouter API with retry and fallback."""
        try:
            resp = await self._client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model", model),
                "tokens_used": data.get("usage", {}).get("total_tokens", 0),
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("OpenRouter rate limit hit, retrying...")
                raise
            # Try fallback model on other errors
            if model != settings.OPENROUTER_FALLBACK_MODEL:
                logger.warning(f"Primary model failed ({e}), trying fallback")
                return await self._call_openrouter(
                    messages, settings.OPENROUTER_FALLBACK_MODEL, max_tokens
                )
            raise

    def _parse_clip_suggestions(self, content: str) -> List[ClipSuggestion]:
        """Parse JSON response into ClipSuggestion objects."""
        try:
            # Strip markdown code fences that some models add despite json_object mode
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()

            data = json.loads(content)
            clips = []
            for item in data.get("clips", []):
                clips.append(
                    ClipSuggestion(
                        start_time=float(item["start_time"]),
                        end_time=float(item["end_time"]),
                        viral_score=int(item.get("viral_score", 50)),
                        titles=item.get("titles", [item.get("title", "Untitled")]),
                        hook_text=item.get("hook_text", ""),
                        description=item.get("description", ""),
                        hashtags=item.get("hashtags", []),
                        thumbnail_prompt=item.get("thumbnail_prompt", ""),
                        reason=item.get("reason", ""),
                    )
                )
            return sorted(clips, key=lambda c: c.viral_score, reverse=True)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {e}\nContent: {content[:500]}")
            return []

    async def close(self):
        await self._client.aclose()
