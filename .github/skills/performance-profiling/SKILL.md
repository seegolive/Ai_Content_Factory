---
name: performance-profiling
description: "Profile and optimize performance bottlenecks in this project. Use when: pipeline is slow, Celery tasks timeout, FFmpeg encoding takes too long, API endpoints are slow, database queries are unoptimized, or memory usage is too high. Covers Celery task profiling, FFmpeg optimization, SQLAlchemy query analysis, and GPU utilization checks."
argument-hint: "e.g. 'pipeline takes 30 min', 'API /videos is slow', 'FFmpeg encoding bottleneck', 'Celery worker high memory'"
---

# Performance Profiling Skill

## When to Use
- Celery pipeline stages timing out or taking unexpectedly long
- FFmpeg encoding is slow (not using GPU / suboptimal settings)
- API endpoints responding slowly
- Database queries taking too long (N+1, missing indexes, no LIMIT)
- High memory usage in Celery worker
- Whisper transcription slow

## Project Performance Context

```
Pipeline budget (typical for 1hr stream):
  Stage 0 (copyright check): <5s
  Stage 1 (Whisper transcription): 3-8 min (GPU), 20-40 min (CPU)
  Stage 2 (AI brain scoring): 15-30s
  Stage 3 (QC): <5s
  Stage 4 (FFmpeg clips): 30-90s per clip
  Stage 5 (review notify): <2s

GPU: RTX 4070 12GB — h264_nvenc for FFmpeg, CUDA for Whisper
CPU fallback: libx264 for FFmpeg, CT2 for Whisper
```

## Procedure

### 1. Check GPU Utilization

```bash
# Is GPU being used by Whisper?
make gpu-test
# or
docker compose exec celery_worker nvidia-smi

# GPU memory in use
docker compose exec celery_worker nvidia-smi --query-gpu=memory.used,memory.free --format=csv
```

### 2. Profile Celery Pipeline Timing

Add timing logs to pipeline stages:

```python
import time

stage_start = time.time()
# ... stage code ...
logger.info(f"[Pipeline] Stage {stage} done in {time.time()-stage_start:.1f}s")
```

Check worker logs:
```bash
docker compose logs celery_worker --tail=100 | grep -E "Stage|done in|ERROR"
```

### 3. FFmpeg Optimization

**Check if GPU encoding is being used:**
```bash
docker compose logs celery_worker --tail=50 | grep -E "h264_nvenc|libx264|encoder"
```

**GPU vs CPU encoding settings:**
```python
# FAST (GPU) — prefer this
["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "28"]

# FALLBACK (CPU) — only if GPU unavailable
["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
```

**Single-pass cut+crop (avoid intermediate files):**
```python
# BAD: cut first, then crop (2 passes, double I/O)
ffmpeg -i input.mp4 -ss 10 -to 60 temp.mp4
ffmpeg -i temp.mp4 [crop_filter] output.mp4

# GOOD: single pass with -ss before -i (fast seek)
ffmpeg -ss 10 -i input.mp4 -t 50 [crop_filter] output.mp4
```

### 4. SQLAlchemy Query Analysis

**Find slow queries — add query logging in `database.py`:**
```python
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
```

**Common N+1 patterns to fix:**
```python
# BAD: N+1
videos = await db.execute(select(Video))
for v in videos.scalars():
    clips = await db.execute(select(Clip).where(Clip.video_id == v.id))  # N queries!

# GOOD: eager load
stmt = select(Video).options(selectinload(Video.clips))
```

**Missing indexes to check:**
```sql
-- Check slow queries
EXPLAIN ANALYZE SELECT * FROM clips WHERE video_id = '...' AND status = 'approved';

-- Add index if missing
CREATE INDEX CONCURRENTLY idx_clips_video_status ON clips(video_id, status);
```

### 5. Whisper Transcription Optimization

```python
# Optimal settings for RTX 4070 12GB
model = WhisperModel(
    "large-v3",
    device="cuda",
    compute_type="float16",   # faster than float32, fits in 12GB
    num_workers=2,
    cpu_threads=4,
)

# For shorter clips / faster throughput
model = WhisperModel(
    "medium",                 # 4x faster than large-v3, 90% accuracy
    device="cuda",
    compute_type="int8_float16",
)
```

### 6. Celery Worker Memory

```bash
# Check worker memory usage
docker stats ai-content-factory-celery_worker-1 --no-stream

# Check if tasks are leaking memory (OOM)
docker compose logs celery_worker | grep -i "oom\|killed\|memory"
```

**Fix memory leak — use `max_tasks_per_child`:**
```python
# celery_app.py
app.conf.worker_max_tasks_per_child = 10  # restart worker after 10 tasks
```

### 7. API Endpoint Profiling

```python
# Add timing middleware to main.py
import time
from fastapi import Request

@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    if duration > 1.0:  # log requests over 1s
        logger.warning(f"SLOW {request.method} {request.url.path} {duration:.2f}s")
    return response
```

## Performance Targets

| Operation | Target | Concern threshold |
|-----------|--------|-------------------|
| API response (read) | <200ms | >1s |
| API response (write) | <500ms | >2s |
| Whisper large-v3 (1hr video, GPU) | <8min | >15min |
| FFmpeg clip cut+crop (GPU) | <30s/clip | >2min |
| AI brain scoring | <30s | >60s |
| DB query (indexed) | <50ms | >500ms |

## Anti-patterns
- Using `compute_type="float32"` for Whisper on GPU (2x slower than float16)
- FFmpeg intermediate temp files (single-pass is always faster)
- `SELECT *` without LIMIT on clips/videos tables
- Synchronous file I/O inside async FastAPI handlers (use `run_in_executor`)
- Loading full video into memory (use streaming / chunk reads)
