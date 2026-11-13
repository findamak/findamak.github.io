#!/bin/bash
# Same main checkout as stock cron: do not strand its commits behind another clone.
set -euo pipefail
export HOME="${HOME:-/home/amak}"
export PATH="/usr/local/bin:/usr/bin:/bin"
export PYTHONDONTWRITEBYTECODE=1
STATE="${FGI_STATE_DIR:-$HOME/.cache/findamak-fear-greed}"
REPO="${FGI_REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
mkdir -p "$STATE"
exec 9>"$STATE/update.lock"
flock -n 9 || exit 0
printf '\n[%s] Fear & Greed refresh starting\n' "$(date -Is)"
cd "$REPO"
[[ "$(git branch --show-current)" == main ]]
sync_remote() {
    git fetch origin main
    if git merge-base --is-ancestor FETCH_HEAD HEAD; then
        return 0  # Includes retrying a previously unpushed local commit.
    fi
    if git merge-base --is-ancestor HEAD FETCH_HEAD; then
        git merge --ff-only FETCH_HEAD
    else
        # Never stash, reset, or incorporate somebody else's uncommitted edits.
        [[ -z "$(git status --porcelain)" ]] || return 1
        git rebase FETCH_HEAD
    fi
}
sync_remote
status=0
/usr/bin/python3 fetch-fear-greed.py || status=$?
# Publish successful assets AND truthful error/stale states for failed ones.
if [[ -n "$(git status --porcelain -- fear-greed.json)" ]]; then
    git add -- fear-greed.json
    git commit --only -m 'Update Fear & Greed readings' -- fear-greed.json
fi
for attempt in 1 2 3; do
    if git push origin HEAD:main; then
        printf '[%s] Fear & Greed published (source status=%s)\n' "$(date -Is)" "$status"
        exit "$status"
    fi
    sync_remote
done
printf 'Fear & Greed push failed after three attempts\n' >&2
exit 1
