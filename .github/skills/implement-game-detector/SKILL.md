---
name: implement-game-detector
description: "Build the missing game_detector.py service. Use when: implementing the game detection service, building the GameDetector class with OpenCV frame sampling, adding game title extraction for pipeline Stage 2 AI scoring. This is Gap #1 — the most critical missing service in the project."
---

# Implement game_detector.py

## Context
`backend/app/services/game_detector.py` does **not exist** yet. It is the most critical missing piece (Gap #1). The pipeline Stage 2 (AI scoring) expects a `GameDetectionResult` with `game_title` and `confidence` to enrich the viral scoring prompt in `ai_brain.py`.

## Read First
- [ai_brain.py](../../ai-content-factory/backend/app/services/ai_brain.py) — how GameDetectionResult is consumed
- [facecam_detector.py](../../ai-content-factory/backend/app/services/facecam_detector.py) — follow same OpenCV singleton pattern
- [pipeline.py](../../ai-content-factory/backend/app/workers/tasks/pipeline.py) — Stage 2, where game detection is called

## Hardware Context
- GPU: NVIDIA RTX 4070 12GB
- OpenCV already available (used in `facecam_detector.py`)
- Can use CUDA-accelerated inference if needed

## Required Output Interface

```python
# What pipeline.py and ai_brain.py expect:
@dataclass
class GameDetectionResult:
    game_title: str          # e.g. "Valorant", "Minecraft", "Unknown"
    confidence: float        # 0.0–1.0
    detected_frames: int     # how many frames had a match
    total_frames_sampled: int
```

## Implementation Approaches

### Approach A: OCR-Based (Recommended for MVP)
Sample N frames from video → extract HUD/UI text via Tesseract OCR → match against known game title list → return top match.

**Pros:** No model training, works for any game with text UI  
**Cons:** Fails for games with no visible text

### Approach B: Visual Classifier (Higher accuracy)
Use a pre-trained CLIP model (`openai/clip-vit-base-patch32`) to embed frames → compare against game reference image embeddings.

**Pros:** More accurate, works without visible text  
**Cons:** Needs reference images per game, heavier compute

### Approach C: Frame-to-LLM (Easiest implementation)
Sample 3–5 frames → encode as base64 → send to vision-capable LLM (GPT-4o / Gemini Vision) → ask "what game is this?"

**Pros:** Zero CV code, works immediately  
**Cons:** Costs tokens, slower, network dependency

## Recommended Implementation (Approach A + C fallback)

```python
# backend/app/services/game_detector.py
import cv2
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_INTERVAL_SECONDS = 30  # sample every 30s
MAX_FRAMES = 10

KNOWN_GAMES = [
    "Valorant", "Minecraft", "Fortnite", "League of Legends",
    "CS2", "Apex Legends", "GTA V", "Among Us", "Roblox",
    # ... extend as needed
]

@dataclass
class GameDetectionResult:
    game_title: str
    confidence: float
    detected_frames: int
    total_frames_sampled: int


class GameDetector:
    """Detects game title from video file via frame sampling + OCR."""

    def __init__(self):
        self._ocr_available = self._check_ocr()

    def _check_ocr(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            logger.warning("[GameDetector] Tesseract not available — OCR disabled")
            return False

    def detect(self, video_path: str) -> GameDetectionResult:
        """Sample frames from video and detect game title."""
        path = Path(video_path)
        if not path.exists():
            logger.error(f"[GameDetector] File not found: {video_path}")
            return GameDetectionResult("Unknown", 0.0, 0, 0)

        frames = self._sample_frames(video_path)
        if not frames:
            return GameDetectionResult("Unknown", 0.0, 0, 0)

        game_votes: dict[str, int] = {}
        for frame in frames:
            title = self._classify_frame(frame)
            if title:
                game_votes[title] = game_votes.get(title, 0) + 1

        if not game_votes:
            return GameDetectionResult("Unknown", 0.0, 0, len(frames))

        best_game = max(game_votes, key=game_votes.get)
        confidence = game_votes[best_game] / len(frames)
        return GameDetectionResult(
            game_title=best_game,
            confidence=confidence,
            detected_frames=game_votes[best_game],
            total_frames_sampled=len(frames),
        )

    def _sample_frames(self, video_path: str) -> list:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        interval = int(fps * SAMPLE_INTERVAL_SECONDS)
        frames = []
        for i in range(0, min(total, interval * MAX_FRAMES), interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
        cap.release()
        return frames

    def _classify_frame(self, frame) -> str | None:
        if self._ocr_available:
            return self._ocr_classify(frame)
        return None  # extend: add LLM fallback here

    def _ocr_classify(self, frame) -> str | None:
        import pytesseract
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray).lower()
        for game in KNOWN_GAMES:
            if game.lower() in text:
                return game
        return None


# Module-level singleton (same pattern as facecam_detector.py)
_detector: GameDetector | None = None

def get_detector() -> GameDetector:
    global _detector
    if _detector is None:
        _detector = GameDetector()
    return _detector


def detect_game(video_path: str) -> GameDetectionResult:
    """Public API — call this from pipeline.py Stage 2."""
    return get_detector().detect(video_path)
```

## Integration in Pipeline Stage 2

In `pipeline.py` Stage 2 (ai_done), add before calling `ai_brain.score_clips()`:
```python
from app.services.game_detector import detect_game, GameDetectionResult

game_result: GameDetectionResult = detect_game(video.file_path)
logger.info(f"[Pipeline] Detected game: {game_result.game_title} (confidence={game_result.confidence:.2f})")
```
Then pass `game_result.game_title` to `ai_brain.score_clips()` for richer context.

## Dependencies to Add
```
# requirements.txt
pytesseract>=0.3.10
# Also needs system package: apt-get install tesseract-ocr
# Add to Dockerfile: RUN apt-get install -y tesseract-ocr
```

## Test File
Create `backend/tests/test_services/test_game_detector.py`:
- Mock `cv2.VideoCapture` to return synthetic frames
- Test with a frame containing game text → assert correct title
- Test with empty video → assert `GameDetectionResult("Unknown", 0.0, ...)`
- Test OCR unavailable → assert graceful fallback
