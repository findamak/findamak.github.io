#!/usr/bin/env bash
# Existing OS cron schedule is unchanged: Tue/Thu 01:00 Australia/Sydney.
set -euo pipefail
export HOME=/home/amak
export HERMES_HOME=/home/amak/.hermes
export PATH=/home/amak/.local/bin:/usr/local/bin:/usr/bin:/bin
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=20'

# Bound the entire fetch/generate/publish job, not just the model request.
if [[ "${1:-}" != --bounded ]]; then
  exec timeout --kill-after=10s 600 bash "$0" --bounded
fi
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
LOCK_FILE="$(git rev-parse --absolute-git-dir)/kids-exercises-update.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -Is) another kids exercise update is running; exiting"
  exit 0
fi
work=''
cleanup() {
  if [[ -n "$work" ]]; then
    git -C "$REPO_DIR" worktree remove --force "$work/tree" || true
    rm -rf -- "$work"
  fi
}
trap cleanup EXIT
trap 'echo "$(date -Is) kids update failed at line $LINENO (status $?)" >&2' ERR
trap 'exit 143' TERM INT
check_source() {
  if [[ "$(git -C "$REPO_DIR" branch --show-current)" != main ]]; then
    echo 'Refusing kids update: source must be on main' >&2
    return 1
  fi
  if [[ -n "$(git -C "$REPO_DIR" status --porcelain --untracked-files=all)" ]]; then
    echo 'Refusing kids update: source is dirty (including staged/untracked files)' >&2
    return 1
  fi
}
check_source
source_head="$(git rev-parse HEAD)"
echo "$(date -Is) starting fresh AI kids exercise update"
git fetch origin main
git merge-base --is-ancestor "$source_head" origin/main || {
  echo 'Refusing to publish: local main has unpublished/divergent commits' >&2
  exit 1
}
base="$(git rev-parse origin/main)"
work="$(mktemp -d /tmp/findamak-kids-publish.XXXXXX)"
# Other cron scripts share the source index: never stage or commit in it.
git worktree add --detach "$work/tree" "$base"
cd "$work/tree"
/usr/bin/python3 scripts/update_kids_exercises.py
git diff --check
# The deterministic generator must only change the two exercise pages.
changed="$(git diff --name-only | sort)"
if [[ "$changed" != $'chiara.html\ncooper.html' ]]; then
  echo "Unexpected generated paths: $changed" >&2
  exit 1
fi
git -c user.name=kids-learning-bot -c user.email=kids-learning-bot@users.noreply.github.com \
  commit --only -m 'Generate fresh kids learning exercises' -- chiara.html cooper.html
commit="$(git rev-parse HEAD)"
check_source
if [[ "$(git -C "$REPO_DIR" rev-parse HEAD)" != "$source_head" ]]; then
  echo 'Source HEAD changed during generation; refusing publish' >&2
  exit 1
fi
# Push this exact isolated commit; never force/rebase over another cron writer.
# If remote main advanced, normal non-fast-forward rejection leaves it untouched.
git push origin "$commit:refs/heads/main"
echo "$(date -Is) pushed $commit; source checkout/index left untouched"
