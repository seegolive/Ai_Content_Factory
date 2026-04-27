#!/usr/bin/env bash
# Pipeline Monitor — prints a notification each time a checkpoint changes
# Usage: ./monitor_pipeline.sh <video_id>
# Example: ./monitor_pipeline.sh 62e89704-82e5-48cd-81b7-53b17324d3a8

VIDEO_ID="${1:-62e89704-82e5-48cd-81b7-53b17324d3a8}"
POLL_INTERVAL=8   # seconds between polls
TIMEOUT=7200      # 2 hours max

# ── Checkpoint index → human label ──────────────────────────────────────────
declare -A STAGE_LABEL=(
  [null]="⏳  Queued / Downloading"
  [input_validated]="✅  Stage 1 done — Input validated & downloaded"
  [transcript_done]="✅  Stage 2 done — Whisper transcription complete"
  [ai_done]="✅  Stage 3 done — AI viral scoring complete"
  [qc_done]="✅  Stage 4 done — QC gate passed"
  [clips_done]="✅  Stage 5 done — FFmpeg clips cut"
  [review_ready]="🎉  Stage 6 done — Review queue ready!"
)

declare -A STAGE_NEXT=(
  [null]="→  Whisper GPU transcription starting…"
  [input_validated]="→  Whisper GPU transcription starting…"
  [transcript_done]="→  AI viral scoring (OpenRouter) starting…"
  [ai_done]="→  QC gate + duration validation starting…"
  [qc_done]="→  FFmpeg clip cutting + subtitle burn starting…"
  [clips_done]="→  Finalizing review queue…"
  [review_ready]=""
)

LAST_CHECKPOINT="__unset__"
LAST_STATUS="__unset__"
ELAPSED=0

TOKEN=$(docker exec ai-content-factory-backend-1 python -c \
  "from app.core.security import create_access_token; print(create_access_token({'sub': 'a4561501-c1b5-4b27-a805-9947d837bebd'}))" 2>/dev/null || echo "")

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          AI CONTENT FACTORY — Pipeline Monitor               ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Video: $VIDEO_ID"
echo "║  Started: $(date '+%H:%M:%S')"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

while [ $ELAPSED -lt $TIMEOUT ]; do
  # ── Query DB directly (faster than API) ──────────────────────────
  ROW=$(docker exec ai-content-factory-postgres-1 psql -U postgres ai_content_factory -t -A \
    -c "SELECT status, COALESCE(checkpoint,'null'), COALESCE(error_message,'') FROM videos WHERE id='$VIDEO_ID';" 2>/dev/null)

  STATUS=$(echo "$ROW" | cut -d'|' -f1)
  CHECKPOINT=$(echo "$ROW" | cut -d'|' -f2)
  ERROR=$(echo "$ROW" | cut -d'|' -f3)

  NOW=$(date '+%H:%M:%S')

  # ── Detect change ─────────────────────────────────────────────────
  if [ "$CHECKPOINT" != "$LAST_CHECKPOINT" ] || [ "$STATUS" != "$LAST_STATUS" ]; then
    LABEL="${STAGE_LABEL[$CHECKPOINT]:-⏳  checkpoint: $CHECKPOINT}"
    NEXT="${STAGE_NEXT[$CHECKPOINT]:-}"

    echo "[$NOW] $LABEL"
    [ -n "$NEXT" ] && echo "       $NEXT"

    # ── File size (only while downloading) ──────────────────────────
    FILE="/home/seego/Ai_Content_Factory/ai-content-factory/storage/videos/${VIDEO_ID}.mp4"
    if [ -f "$FILE" ]; then
      SIZE=$(du -sh "$FILE" 2>/dev/null | cut -f1)
      echo "       📦 File size: $SIZE"
    fi

    # ── Clips summary (when done) ────────────────────────────────────
    if [ "$CHECKPOINT" = "clips_done" ] || [ "$CHECKPOINT" = "review_ready" ]; then
      CLIPS=$(docker exec ai-content-factory-postgres-1 psql -U postgres ai_content_factory -t -A \
        -c "SELECT COUNT(*), ROUND(AVG(viral_score)::numeric,1), MAX(viral_score) FROM clips WHERE video_id='$VIDEO_ID';" 2>/dev/null)
      CLIP_COUNT=$(echo "$CLIPS" | cut -d'|' -f1)
      AVG_SCORE=$(echo "$CLIPS" | cut -d'|' -f2)
      MAX_SCORE=$(echo "$CLIPS" | cut -d'|' -f3)
      echo "       🎬 Clips: $CLIP_COUNT generated | avg score: $AVG_SCORE | best: $MAX_SCORE"
    fi

    LAST_CHECKPOINT="$CHECKPOINT"
    LAST_STATUS="$STATUS"
    echo ""
  fi

  # ── Terminal states ───────────────────────────────────────────────
  if [ "$STATUS" = "error" ]; then
    echo "[$NOW] ❌ PIPELINE FAILED"
    echo "       Error: $ERROR"
    echo ""
    # Show last 20 worker logs for diagnosis
    echo "── Last worker logs ──"
    docker logs ai-content-factory-celery_worker-1 2>&1 | grep -E "$VIDEO_ID|ERROR|Stage|checkpoint" | tail -20
    exit 1
  fi

  if [ "$STATUS" = "review" ] || [ "$CHECKPOINT" = "review_ready" ]; then
    echo "[$NOW] ✅ PIPELINE COMPLETE — Video is in review queue"
    echo ""

    # Full clips summary
    echo "── Clips Summary ──────────────────────────────────────────────"
    docker exec ai-content-factory-postgres-1 psql -U postgres ai_content_factory \
      -c "SELECT SUBSTRING(title,1,40) AS title, ROUND(duration_seconds) AS dur_s, viral_score, moment_type, review_status FROM clips WHERE video_id='$VIDEO_ID' ORDER BY viral_score DESC;"
    echo ""

    # Final video row
    echo "── Video Record ───────────────────────────────────────────────"
    docker exec ai-content-factory-postgres-1 psql -U postgres ai_content_factory \
      -c "SELECT title, status, checkpoint, ROUND(duration_seconds) AS dur_s, clips_count FROM videos WHERE id='$VIDEO_ID';"
    echo ""
    echo "Open review queue: http://localhost:3000/review"
    exit 0
  fi

  # ── Periodic progress line (every 30s) ───────────────────────────
  if [ "$ELAPSED" -gt 0 ] && [ $(( ELAPSED % 30 )) -eq 0 ]; then
    FILE="/home/seego/Ai_Content_Factory/ai-content-factory/storage/videos/${VIDEO_ID}.mp4"
    FSIZE=""
    [ -f "$FILE" ] && FSIZE=" | file: $(du -sh "$FILE" 2>/dev/null | cut -f1)"
    # Recent worker log (|| true prevents grep exit-1 from killing script)
    LAST_LOG=$(docker logs --since 35s ai-content-factory-celery_worker-1 2>&1 | grep -v "^$" | grep -v "^\[" | tail -1 || true)
    echo "[$NOW] ⏳ still $STATUS / $CHECKPOINT$FSIZE"
    [ -n "$LAST_LOG" ] && echo "       $LAST_LOG"
    echo ""
  fi

  sleep $POLL_INTERVAL
  ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

echo "[$(date '+%H:%M:%S')] ⏰ Monitor timed out after ${TIMEOUT}s"
exit 2
