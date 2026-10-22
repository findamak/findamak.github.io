# Fresh kids learning exercises

The existing OS cron entry still runs `scripts/update_kids_exercises_and_push.sh`
**Tuesday and Thursday at 01:00 Australia/Sydney**. No scheduler changes are needed.
There is no date-parity selection, fixed question bank, or preset fallback.

## Generation and validation

`update_kids_exercises.py` invokes the installed `/home/amak/.local/bin/hermes`
once per run using its existing configured provider/authentication. No new API
credentials are required. It provides only the current questions, age/curriculum
instructions and a fresh run nonce. The subprocess has a minimal explicit
cron-safe environment, including `HOME=/home/amak` and
`HERMES_HOME=/home/amak/.hermes` (never `.openclaw`).

The locally inspected CLI supports `-z` (only final response on stdout) and
`--ignore-rules` (no ambient instructions, skills or memory). `--toolsets
context_engine` selects the installed built-in empty toolset; its resolved tool
list was verified as `[]`. The model cannot run shell/git/file tools. It runs in a
temporary directory, with stdout/stderr captured in temporary files. The Python
controller, not the model, owns validation and page updates. The model subprocess
has a 300-second timeout and its process group is killed on timeout. Real stderr,
nonzero exit status, JSON failures and validation errors are logged; no guessed or
preset content is substituted on failure. There are no unbounded retries.

Each set must contain exactly **10 questions per child**. The prompt prioritises:

- **Chiara, 8:** three numeracy, three spelling, two grammar/punctuation, and two
  reading/reasoning questions, with Australian spelling and NAPLAN-style skills.
- **Cooper, 5:** foundational letters/sounds/words and numeracy, plus variety such
  as shapes, patterns, simple stories and kindness.

The validator checks the entire batch before either page is touched: exact keys
and question schemas, supported types, count, unique new questions (against both
currently published sets, normalised for case/spacing/.!?), printable ASCII,
nonempty bounded text, four unique choice options, exact answer membership and
valid typed-answer aliases. It rejects `<` to prevent inline-script breakouts.
JSON is inserted by slicing, so backslashes cannot be interpreted as regex
replacement escapes. Legacy JS checks exclude the data array (words such as
`violet` are not mistaken for `let` declarations).

Choices use A/B/C/D prefixes because the legacy answer comparator ignores case and
`.!?`; punctuation-only distractors without labels could otherwise all score as
correct. The validator rejects any options colliding under that comparator.
Curriculum distribution, semantic correctness, and substantially different
contexts are model instructions, not mathematical guarantees. Structural validation
cannot prove every educational answer correct or detect every paraphrase. Exact
normalised reuse of the current set is rejected; there is no all-history archive.

Both page replacements are staged before rename; concurrent page edits abort,
and ordinary IO failures roll back already-replaced pages. A process/machine crash
between two renames is not a filesystem-wide transaction. The scheduled path uses
an isolated worktree, so such a failure never publishes a partial set. Outside the
exercise JSON, only the ES5 content-hash progress key was changed: reloading an
unchanged set retains progress, while fresh sets start at zero.

## Safe publication

The wrapper uses `flock` and a 600-second overall timeout (10-second kill grace).
It refuses a non-main, dirty, staged or untracked source checkout and refuses local
unpublished/divergent commits. It fetches `origin/main`, creates a temporary
detached worktree, generates and validates there, checks that only the two pages
changed, and commits only those page paths with per-command author settings.
It rechecks the source branch, cleanliness and HEAD before pushing the exact
isolated commit to `origin/main`. It never uses the shared source index to stage
or commit, never changes persistent git identity, and never force-pushes or
rebases over a competing cron writer. A remote race fails visibly rather than
publishing stale content. Temporary worktrees are removed on success/failure.

**The source checkout/index is deliberately left untouched after a scheduled
push**, so its local main may be behind origin/main until the next normal
`git pull --ff-only`. This avoids racing other cron scripts sharing that checkout.
The scheduled publication is built directly from fetched origin/main, not stale
local page content. Logs continue through stdout/stderr to the existing cron log.
If a run is skipped/failed, inspect that log; fix provider/auth or local git state
and rerun the existing wrapper. Never bypass dirty-state checks or force-push.

## Manual review / local-only operation

```sh
# Generate real AI content and validate without changing pages or git:
env -i HOME=/home/amak PATH=/usr/bin:/bin \
  /usr/bin/python3 scripts/update_kids_exercises.py \
  --check --output /tmp/kids-review.json

# Review the JSON, then apply through the same validator (no AI call, no git):
/usr/bin/python3 scripts/update_kids_exercises.py --input /tmp/kids-review.json

# Generate, validate, and update locally in one step (no git):
/usr/bin/python3 scripts/update_kids_exercises.py
```

`--output` must be outside the page repository. `--root` can target a temporary
copy/worktree. Reapplying the same batch fails the freshness check as intended.
Do not run the publishing wrapper when you only want a local test.

## Tests

```sh
/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py'
bash -n scripts/update_kids_exercises_and_push.sh
node --test tests/cgt-calculations.test.js tests/pathfire-calculations.test.js
```

Kids tests cover malformed/repeated/unsafe data, both-pages-before-write behaviour,
backslash preservation, CLI check/failure/apply paths, timeout and real error
propagation using an explicit test executable, progress-key changes via Node,
legacy token false positives, and isolated git publication against a disposable
local bare repository (including dirty/staged/non-main refusal). Test fixtures are
not used as live generation evidence. Live verification generated a real fresh
20-question set using the installed Hermes CLI in a sparse environment; it passed
validation and was then applied locally for UI/grading checks.

CLI reference: https://hermes-agent.nousresearch.com/docs/reference/cli-commands
