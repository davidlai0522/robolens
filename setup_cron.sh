#!/usr/bin/env bash
# setup_cron.sh — Install a daily cron job that runs the JarvisForResearchers pipeline
#
# The schedule is read from config.yaml (discovery.cron_schedule).
# Defaults to 08:00 every morning if config.yaml is missing.
#
# Run once:  bash setup_cron.sh
# Remove:    bash setup_cron.sh --remove

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV="$HOME/.local/bin/uv"
LOG_DIR="$REPO_DIR/logs"
CRON_TAG="# jarvis-for-researchers-daily"

# Read schedule from config.yaml via uv; fall back to default
CRON_SCHEDULE=$("$UV" run python3 -c \
  "import yaml; c=yaml.safe_load(open('$REPO_DIR/config.yaml')); print(c.get('discovery',{}).get('cron_schedule','0 8 * * *'))" \
  2>/dev/null || echo "0 8 * * *")

CRON_JOB="$CRON_SCHEDULE cd \"$REPO_DIR\" && mkdir -p \"$LOG_DIR\" && \"$UV\" run python pipeline/run.py --daily >> \"$LOG_DIR/daily.log\" 2>&1 $CRON_TAG"

if [[ "$1" == "--remove" ]]; then
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab -
    echo "✅ JarvisForResearchers daily cron removed."
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
