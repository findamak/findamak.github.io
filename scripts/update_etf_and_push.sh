#!/usr/bin/env bash
# Daily issuer refresh in the shared checkout. Only etf.html is committed.
set -euo pipefail
export HOME="${HOME:-/home/amak}"
export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:/home/amak/.local/bin"
export PYTHONDONTWRITEBYTECODE=1
REPO_DIR="${ETF_REPO_DIR:-/home/amak/findamak.github.io}"
PYTHON="${ETF_PYTHON:-/usr/bin/python3}"
exec 9>"${HOME}/.findamak-etf-update.lock"
if ! flock -n 9; then
  printf '%s another ETF update is running\n' "$(date -Is)"
  exit 0
fi
cd "$REPO_DIR"
if [[ "${1:-}" == "--check" ]]; then
  "$PYTHON" -c 'import bs4, curl_cffi; from zoneinfo import ZoneInfo; ZoneInfo("Australia/Sydney")'
  command -v pdftotext
  "$PYTHON" -m unittest discover -s tests -p 'test*etf*.py' -v
  exit 0
fi
[[ $# == 0 ]] || { printf 'Usage: %s [--check]\n' "$0" >&2; exit 2; }
[[ "$(git branch --show-current)" == main ]] || { printf 'Refusing non-main branch\n' >&2; exit 1; }
# Never consume someone's manual edits or staged ETF change.
git diff --quiet -- etf.html && git diff --cached --quiet -- etf.html || {
  printf 'etf.html has uncommitted changes; refusing overwrite\n' >&2; exit 1;
}
printf '%s starting ETF issuer refresh\n' "$(date -Is)"
git pull --ff-only origin main
refresh_status=0
"$PYTHON" scripts/update_etf.py || refresh_status=$?
# Publish the visible stale/error marker even after source failure, but preserve
# the updater's nonzero exit status for cron monitoring.
if ! git diff --quiet -- etf.html; then
  git -c user.name=etf-bot -c user.email=etf-bot@users.noreply.github.com \
    commit --only -m 'Refresh ETF issuer metrics and status' -- etf.html
fi
for attempt in 1 2 3; do
  if git push origin HEAD:main; then
    printf '%s ETF publication finished; updater exit=%s\n' "$(date -Is)" "$refresh_status"
    exit "$refresh_status"
  fi
  # Do not force-push, stash another job's changes, or rebase a dirty index.
  git diff --quiet && git diff --cached --quiet || {
    printf 'Push raced with another job; dirty checkout, committed ETF change retained for retry\n' >&2; exit 1;
  }
  git fetch origin main
  if ! git -c user.name=etf-bot -c user.email=etf-bot@users.noreply.github.com rebase origin/main; then
    git rebase --abort
    printf 'Rebase conflict; local committed update retained, no force push\n' >&2
    exit 1
  fi
done
printf 'Push retries exhausted; local commit retained\n' >&2
exit 1
