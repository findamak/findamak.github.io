#!/usr/bin/env bash
# Cron-safe daily refresh for Chiara and Cooper's learning exercises.
# Chiara's rotations prioritise numeracy, spelling, grammar, and punctuation.

set -euo pipefail

REPO_DIR="/home/amak/findamak.github.io"
PYTHON="/usr/bin/python3"
LOCK_FILE="/tmp/findamak-kids-exercises-update.lock"

export HOME="/home/amak"
export PATH="/usr/local/bin:/usr/bin:/bin:/home/amak/.local/bin"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Is) another kids exercise update is already running; exiting"
  exit 0
fi

cd "${REPO_DIR}"
echo "$(date -Is) starting kids exercise update"

git pull --ff-only
"${PYTHON}" scripts/update_kids_exercises.py

# Guard the legacy iPad compatibility contract before publishing.
"${PYTHON}" - <<'PY'
from pathlib import Path
import json, re
for page in ('chiara.html', 'cooper.html'):
    html = Path(page).read_text(encoding='utf-8')
    scripts = '\n'.join(re.findall(r'<script>(.*?)</script>', html, flags=re.S))
    match = re.search(r'var exercises = (\[.*?\]);', scripts, flags=re.S)
    if not match:
        raise SystemExit(page + ': missing exercises array')
    if len(json.loads(match.group(1))) != 10:
        raise SystemExit(page + ': expected 10 exercises')
    forbidden = ('const ', 'let ', '=>', '`', 'classList', 'forEach(', 'append(')
    found = [token for token in forbidden if token in scripts]
    if found:
        raise SystemExit(page + ': unsupported modern JS: ' + ', '.join(found))
    if any(ord(ch) > 127 for ch in scripts):
        raise SystemExit(page + ': non-ASCII script content')
PY

git diff --check
git add chiara.html cooper.html
if git diff --cached --quiet; then
  echo "$(date -Is) no kids exercise changes to commit"
else
  git config user.name "kids-learning-bot"
  git config user.email "kids-learning-bot@users.noreply.github.com"
  git commit -m "Update kids learning exercises"
  git push
  echo "$(date -Is) pushed kids exercise update"
fi

echo "$(date -Is) finished kids exercise update"
