#!/usr/bin/env bash
# Cron-safe updater for https://findamak.github.io/btc.html.
# Regenerates data/btcusd.json, commits it if changed, and pushes to GitHub.

set -euo pipefail

REPO_DIR="/home/amak/findamak.github.io"
PYTHON="/usr/bin/python3"
LOCK_FILE="/tmp/findamak-btcusd-ema-update.lock"
NOTIFIED_CROSS_STATE="/home/amak/scripts/btcusd-ema-notified-cross.json"

export HOME="/home/amak"
export PATH="/usr/local/bin:/usr/bin:/bin:/home/amak/.local/bin"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Is) another BTCUSD EMA update is already running; exiting"
  exit 0
fi

cd "${REPO_DIR}"

echo "$(date -Is) starting BTCUSD EMA update"

# Keep the local checkout current before generating data.
git pull --ff-only

# Generate the static JSON payload.
"${PYTHON}" scripts/update_btcusd_ema.py

# Commit only the generated data file. If Bitstamp returns identical market data
# but updated_at changed, this still records that the cron job completed successfully.
git add data/btcusd.json

if git diff --cached --quiet; then
  echo "$(date -Is) no BTCUSD data changes to commit"
else
  git config user.name "btc-ema-bot"
  git config user.email "btc-ema-bot@users.noreply.github.com"
  git commit -m "Update BTCUSD EMA data"
  git push
  echo "$(date -Is) pushed BTCUSD EMA data update"
fi

# Send an email only when the newest EMA crossover is newer than the most recent
# successfully notified crossover. Notification failure is logged but does not
# block the data update or GitHub Pages deploy; because state is updated only
# after a successful email, the next cron run will retry failed notifications.
if ! "${PYTHON}" scripts/notify_btcusd_crossover.py data/btcusd.json "${NOTIFIED_CROSS_STATE}"; then
  echo "$(date -Is) warning: BTCUSD crossover email notification failed" >&2
fi

echo "$(date -Is) finished BTCUSD EMA update"
