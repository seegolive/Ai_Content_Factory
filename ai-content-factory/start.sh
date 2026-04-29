#!/usr/bin/env bash
# =============================================================================
#  AI Content Factory — start.sh
#  Menjalankan semua service + menu interaktif
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# =============================================================================
# HEADER
# =============================================================================
print_header() {
  echo -e "${CYAN}"
  echo "  ╔═══════════════════════════════════════════╗"
  echo "  ║   🏭  AI CONTENT FACTORY                 ║"
  echo "  ║   Automated Video → Clips Pipeline       ║"
  echo "  ╚═══════════════════════════════════════════╝"
  echo -e "${RESET}"
}

# =============================================================================
# CHECK SERVICES STATUS
# =============================================================================
check_status() {
  echo -e "${BOLD}Status Container:${RESET}"
  docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | \
    sed "s/running/${GREEN}running${RESET}/g; s/healthy/${GREEN}healthy${RESET}/g; s/unhealthy/${RED}unhealthy${RESET}/g"
}

# =============================================================================
# START SERVICES
# =============================================================================
start_services() {
  local rebuild=$1
  echo -e "${CYAN}Menjalankan semua service...${RESET}"
  if [[ "$rebuild" == "rebuild" ]]; then
    echo -e "${YELLOW}Rebuilding frontend image...${RESET}"
    docker compose build frontend
  fi
  docker compose up -d
  echo ""
  echo -e "${GREEN}✓ Semua service berjalan!${RESET}"
  echo ""
  sleep 2
  check_status
  echo ""
  echo -e "${BOLD}URL:${RESET}"
  echo -e "  Frontend  → ${CYAN}http://localhost:3000${RESET}"
  echo -e "  Backend   → ${CYAN}http://localhost:8000${RESET}"
  echo -e "  API Docs  → ${CYAN}http://localhost:8000/docs${RESET}"
  echo -e "  Flower    → ${CYAN}http://localhost:5555${RESET}"
}

# =============================================================================
# LOG VIEWER
# =============================================================================
show_logs_menu() {
  echo ""
  echo -e "${BOLD}Pilih log yang ingin dilihat:${RESET}"
  echo "  1) Semua service (all)"
  echo "  2) Pipeline worker (celery_worker)"
  echo "  3) Backend API (backend)"
  echo "  4) Frontend (frontend)"
  echo "  5) Database (postgres)"
  echo "  6) Redis"
  echo "  7) Pipeline saja (filter: Stage/ERROR/mode)"
  echo "  8) Download progress saja"
  echo "  9) Kembali ke menu utama"
  echo ""
  read -rp "Pilihan [1-9]: " log_choice

  case $log_choice in
    1)
      echo -e "${CYAN}Showing all logs (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f --tail=50 2>/dev/null
      ;;
    2)
      echo -e "${CYAN}Showing celery_worker logs (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f --tail=100 celery_worker 2>/dev/null
      ;;
    3)
      echo -e "${CYAN}Showing backend logs (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f --tail=100 backend 2>/dev/null
      ;;
    4)
      echo -e "${CYAN}Showing frontend logs (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f --tail=100 frontend 2>/dev/null
      ;;
    5)
      echo -e "${CYAN}Showing postgres logs (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f --tail=50 postgres 2>/dev/null
      ;;
    6)
      echo -e "${CYAN}Showing redis logs (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f --tail=50 redis 2>/dev/null
      ;;
    7)
      echo -e "${CYAN}Showing pipeline logs (Stage/ERROR/checkpoint) — realtime (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f celery_worker 2>/dev/null | grep --line-buffered -E "Stage|ERROR|checkpoint|mode=|Pipeline|ready|TASK|SUCCESS|FAILURE|clip|transcript|whisper"
      ;;
    8)
      echo -e "${CYAN}Showing download progress — realtime (Ctrl+C untuk keluar)...${RESET}"
      docker compose logs -f celery_worker 2>/dev/null | grep --line-buffered -E "download|ETA|GiB|MiB"
      ;;
    9)
      return
      ;;
    *)
      echo -e "${RED}Pilihan tidak valid.${RESET}"
      ;;
  esac
}

# =============================================================================
# STOP SERVICES
# =============================================================================
stop_services() {
  echo -e "${YELLOW}Menghentikan semua service...${RESET}"
  docker compose down
  echo -e "${GREEN}✓ Semua service dihentikan.${RESET}"
}

# =============================================================================
# DB QUICK STATS
# =============================================================================
show_db_stats() {
  echo -e "${BOLD}Database Stats:${RESET}"
  docker compose exec postgres psql -U postgres -d ai_content_factory -c \
    "SELECT
       (SELECT COUNT(*) FROM videos) AS total_videos,
       (SELECT COUNT(*) FROM videos WHERE status='review') AS review_ready,
       (SELECT COUNT(*) FROM videos WHERE status='processing') AS processing,
       (SELECT COUNT(*) FROM videos WHERE status='error') AS errors,
       (SELECT COUNT(*) FROM clips) AS total_clips,
       (SELECT COUNT(*) FROM clips WHERE status='approved') AS approved_clips;" 2>/dev/null \
    || echo -e "${RED}Database tidak dapat dijangkau.${RESET}"
}

# =============================================================================
# MAIN MENU
# =============================================================================
main_menu() {
  while true; do
    print_header
    echo -e "${BOLD}Menu Utama:${RESET}"
    echo "  1) Start services (gunakan image yang ada)"
    echo "  2) Start + rebuild frontend (code terbaru)"
    echo "  3) Lihat status container"
    echo "  4) Lihat log"
    echo "  5) Lihat statistik database"
    echo "  6) Stop semua service"
    echo "  7) Keluar"
    echo ""
    read -rp "Pilihan [1-7]: " choice

    case $choice in
      1)
        start_services
        ;;
      2)
        start_services rebuild
        ;;
      3)
        echo ""
        check_status
        echo ""
        read -rp "Tekan Enter untuk kembali..."
        ;;
      4)
        show_logs_menu
        ;;
      5)
        echo ""
        show_db_stats
        echo ""
        read -rp "Tekan Enter untuk kembali..."
        ;;
      6)
        stop_services
        echo ""
        read -rp "Tekan Enter untuk kembali..."
        ;;
      7)
        echo -e "${GREEN}Bye!${RESET}"
        exit 0
        ;;
      *)
        echo -e "${RED}Pilihan tidak valid.${RESET}"
        sleep 1
        ;;
    esac

    echo ""
  done
}

# =============================================================================
# ENTRY POINT — support argumen langsung
# =============================================================================
case "${1:-}" in
  start)        start_services ;;
  start-build)  start_services rebuild ;;
  stop)         stop_services ;;
  status)       check_status ;;
  logs)         docker compose logs -f --tail=50 2>/dev/null ;;
  logs-worker)  docker compose logs -f --tail=100 celery_worker 2>/dev/null ;;
  logs-pipeline)
    docker compose logs -f celery_worker 2>/dev/null | grep --line-buffered -E "Stage|ERROR|checkpoint|mode=|Pipeline|SUCCESS|FAILURE|clip|transcript"
    ;;
  db-stats)     show_db_stats ;;
  *)            main_menu ;;
esac
