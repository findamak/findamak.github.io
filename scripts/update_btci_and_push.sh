#!/usr/bin/env bash
# Cron-safe updater for https://findamak.github.io/btci.html.
# Regenerates data/btci.json, commits it if changed, and pushes to GitHub.

set -euo pipefail

REPO_DIR="/home/amak/findamak.github.io"
PYTHON="/usr/bin/python3"
LOCK_FILE="/tmp/findamak-btci-update.lock"

export HOME="/home/amak"
export PATH="/usr/local/bin:/usr/bin:/bin:/home/amak/.local/bin"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Is) another BTCI performance update is already running; exiting"
  exit 0
fi

cd "${REPO_DIR}"

echo "$(date -Is) starting BTCI performance update"

# Keep the local checkout current before generating data.
git pull --ff-only

# Generate the static JSON payload.
"${PYTHON}" scripts/update_btci.py

# Commit only the generated BTCI data file. updated_at changes on each
# successful run so this records cron completion as well as market updates.
git add data/btci.json

if git diff --cached --quiet; then
  echo "$(date -Is) no BTCI data changes to commit"
else
  git config user.name "btci-bot"
  git config user.email "btci-bot@users.noreply.github.com"
  git commit -m "Update BTCI performance data"
  git push
  echo "$(date -Is) pushed BTCI performance data update"
fi

echo "$(date -Is) finished BTCI performance update"
