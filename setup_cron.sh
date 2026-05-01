#!/usr/bin/env bash
# setup_cron.sh — Install a daily cron job that runs the RoboLens pipeline
#
# Runs at 08:00 every morning. Logs to logs/daily.log.
# Run once: bash setup_cron.sh
# Remove:   bash setup_cron.sh --remove

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV="$HOME/.local/bin/uv"
LOG_DIR="$REPO_DIR/logs"
CRON_TAG="# robolens-daily"
CRON_JOB="0 8 * * * cd \"$REPO_DIR\" && mkdir -p \"$LOG_DIR\" && \"$UV\" run python pipeline/run.py --daily >> \"$LOG_DIR/daily.log\" 2>&1 $CRON_TAG"

if [[ "$1" == "--remove" ]]; then
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab -
    echo "✅ RoboLens daily cron removed."
    exit 0
fi

# Avoid duplicate entries
if crontab -l 2>/dev/null | grep -q "$CRON_TAG"; then
    echo "⚠️  Cron job already installed. Run with --remove to uninstall first."
    exit 0
fi

mkdir -p "$LOG_DIR"
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
echo "✅ Daily cron installed — runs at 08:00 every morning."
echo "   Logs: $LOG_DIR/daily.log"
echo "   Remove with: bash setup_cron.sh --remove"
