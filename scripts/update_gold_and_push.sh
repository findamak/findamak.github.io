#!/usr/bin/env bash
# Cron-safe updater for https://findamak.github.io/gold.html.
# Regenerates KGLD/IGLD/IAUI versus GLD comparison data, commits it if changed, and pushes to GitHub.

set -euo pipefail

REPO_DIR="/home/amak/findamak.github.io"
PYTHON="/usr/bin/python3"
LOCK_FILE="/tmp/findamak-gold-update.lock"

export HOME="/home/amak"
export PATH="/usr/local/bin:/usr/bin:/bin:/home/amak/.local/bin"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Is) another KGLD/IGLD/IAUI versus GLD update is already running; exiting"
  exit 0
fi

cd "${REPO_DIR}"

echo "$(date -Is) starting KGLD/IGLD/IAUI versus GLD update"

git pull --ff-only

"${PYTHON}" scripts/update_gold.py

git add data/gold.json

if git diff --cached --quiet; then
  echo "$(date -Is) no KGLD/IGLD/IAUI versus GLD data changes to commit"
else
  git config user.name "gold-etf-bot"
  git config user.email "gold-etf-bot@users.noreply.github.com"
  git commit -m "Update gold ETF performance data"
  git push
  echo "$(date -Is) pushed KGLD/IGLD/IAUI versus GLD data update"
fi

echo "$(date -Is) finished KGLD/IGLD/IAUI versus GLD update"
