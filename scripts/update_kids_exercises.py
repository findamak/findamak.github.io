#!/usr/bin/env python3
"""Generate and validate fresh exercises; never perform git operations."""
import argparse
import json
import logging
import os
import re
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHILDREN = ('chiara', 'cooper')


def extract_exercises(html):
    markers = list(re.finditer(r'var exercises\s*=\s*', html))
    if len(markers) != 1:
        raise ValueError('Expected one unique var exercises array')
    start = markers[0].end()
    data, length = json.JSONDecoder().raw_decode(html[start:])
    end = start + length
    if not isinstance(data, list) or html[end:end + 1] != ';':
        raise ValueError('Expected exercises JSON array followed by semicolon')
    return data, start, end


def prepare_updates(root, batch):
    originals = {c: (root / (c + '.html')).read_bytes() for c in CHILDREN}
    parsed = {c: extract_exercises(b.decode('utf-8')) for c, b in originals.items()}
    validate_batch(batch, {c: p[0] for c, p in parsed.items()})
    updates = {}
    for child in CHILDREN:
        html = originals[child].decode('utf-8')
        _, start, end = parsed[child]
        # Check only executable code, not words such as 'violet ' in JSON.
        code_html = html[:start] + '[]' + html[end:]
        scripts = '\n'.join(re.findall(r'<script>(.*?)</script>', code_html, re.S))
        forbidden = (r'\b(?:const|let)\s', r'=>', r'`', r'\bclassList\b',
                     r'\bforEach\s*\(', r'\bappend\s*\(', r'\bSet\s*\(', r'\bArray\.isArray\s*\(')
        if any(re.search(token, scripts) for token in forbidden) or not scripts.isascii():
            raise ValueError(child + ': legacy iPad compatibility check failed')
        # Slicing (not regex replacement) preserves literal backslashes.
        updated = html[:start] + json.dumps(batch[child], indent=2, ensure_ascii=True) + html[end:]
        updates[root / (child + '.html')] = (originals[child], updated.encode('utf-8'))
    return updates


def publish_updates(updates):
    """Stage both files first; reject concurrent edits and roll back IO failures."""
    staged = {}
    replaced = []
    try:
        for page, (before, after) in updates.items():
            if page.read_bytes() != before:
                raise ValueError('Page changed during generation: ' + str(page))
            fd, name = tempfile.mkstemp(prefix='.kids-', dir=page.parent)
            staged[page] = Path(name)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, page.stat().st_mode & 0o777)
        for page, (before, _) in updates.items():
            if page.read_bytes() != before:
                raise ValueError('Concurrent page edit: ' + str(page))
        for page, name in staged.items():
            os.replace(name, page)
            replaced.append(page)
    except BaseException:
        for page in replaced:
            page.write_bytes(updates[page][0])
        raise
    finally:
        for name in staged.values():
            name.unlink(missing_ok=True)


def generate_batch(previous, executable='/home/amak/.local/bin/hermes', timeout=300):
    prompt = '''Create a genuinely NEW set of Australian primary-school exercises.
Return ONLY a JSON object with exactly two keys: chiara and cooper, each an array
of exactly 10 exercises. No markdown fences, explanation, tools or file operations.
Each exercise has type (choice or input), title, question, prompt, answer.
Choice: exactly four string options, answer is one option verbatim.
Input: options is [], answer is a string or list of 1-6 distinct accepted strings.
All strings must be nonempty printable ASCII; no '<' or Unicode. No other fields.
Each question must be unique across the batch and DIFFERENT from every old question
below, not just changing punctuation/case. Use new contexts, numbers and words.
Chiara age 8: 3 numeracy (varied), 3 spelling, 2 grammar/punctuation, 2 reading or
reasoning. Prioritise NAPLAN-style skills at a suitable Year 3 level. Australian
spelling. Cooper age 5: foundational literacy (sounds, letters, simple words),
numeracy (counting, small addition/subtraction), plus shapes/patterns/story/kindness.
Keep questions short and self-contained. No unavailable pictures or audio.
Check every answer, spelling clue and calculation internally; exactly one correct
choice, unambiguous questions, helpful prompts, not merely the answer repeated.
IMPORTANT: prefix ALL choice options with distinct 'A) ', 'B) ', 'C) ', 'D) '.
The answer must include that prefix too. The page ignores case and .!? when grading,
so prefixes are essential for punctuation distractors. Input aliases must be distinct
when lowercased, trimmed, whitespace collapsed and .!? removed.
Questions requiring punctuation-only answers must use labelled choices instead of input.
Do not reuse fixed presets or just paraphrase the old set. Vary answer positions.
'''
    prompt += '\nRun nonce: ' + str(uuid.uuid4()) + '\nOld questions (do not reuse):\n'
    prompt += json.dumps({c: [q['question'] for q in rows] for c, rows in previous.items()})
    # context_engine is the installed CLI's built-in empty toolset (resolved to []).
    # --ignore-rules prevents ambient AGENTS.md, memories and skills entering the task.
    command = [executable, '--ignore-rules', '--toolsets', 'context_engine', '-z', prompt]
    env = {'HOME': '/home/amak', 'HERMES_HOME': '/home/amak/.hermes',
           'PATH': '/home/amak/.local/bin:/usr/local/bin:/usr/bin:/bin',
           'LANG': 'C.UTF-8', 'TZ': 'Australia/Sydney', 'HERMES_MAX_ITERATIONS': '2'}
    with tempfile.TemporaryDirectory(prefix='kids-generation-') as work:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, start_new_session=True)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                err.seek(0)
                raise RuntimeError('Hermes timed out: ' + err.read().decode('utf-8', 'replace'))
            err.seek(0)
            errors = err.read().decode('utf-8', 'replace')
            if errors.strip():
                logging.warning('Hermes stderr: %s', errors.strip())
            if proc.returncode:
                raise RuntimeError('Hermes exited %s: %s' % (proc.returncode, errors))
            out.seek(0)
            raw = out.read(100001)
            if len(raw) > 100000:
                raise ValueError('Hermes response exceeded 100KB')
            try:
                return json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise ValueError('Hermes did not return strict JSON: ' + raw[:500].decode('utf-8', 'replace')) from exc



def normalise(value):
    """Match the legacy page's answer comparison (also useful for freshness)."""
    return re.sub(r'\s+', ' ', re.sub(r'[.!?]', '', value.strip().lower()))


def validate_batch(batch, previous):
    if not isinstance(batch, dict) or set(batch) != set(CHILDREN):
        raise ValueError('Expected exactly chiara and cooper')
    old = {normalise(q['question']) for rows in previous.values() for q in rows}
    seen = set()
    def text(value):
        if (not isinstance(value, str) or not value.strip() or len(value) > 1000
                or any(ord(c) < 32 or ord(c) > 126 for c in value) or '<' in value):
            raise ValueError('Expected nonempty printable ASCII text without < (max 1000 chars)')
    for child in CHILDREN:
        rows = batch[child]
        if not isinstance(rows, list) or len(rows) != 10:
            raise ValueError(child + ': expected exactly 10 questions')
        for q in rows:
            if not isinstance(q, dict) or q.get('type') not in ('choice', 'input'):
                raise ValueError(child + ': unknown question type')
            required = {'type', 'title', 'question', 'prompt', 'answer'}
            if not required <= set(q) or set(q) - required - {'options'}:
                raise ValueError(child + ': incorrect question schema')
            for field in ('title', 'question', 'prompt'):
                text(q[field])
            key = normalise(q['question'])
            if key in old or key in seen:
                raise ValueError(child + ': repeated question: ' + q['question'])
            seen.add(key)
            if q['type'] == 'choice':
                options = q.get('options')
                if not isinstance(options, list) or len(options) != 4:
                    raise ValueError('Choice needs four options')
                for option in options:
                    text(option)
                if len({normalise(o) for o in options}) != len(options):
                    raise ValueError('Options collide under legacy answer comparison')
                text(q['answer'])
                if q['answer'] not in options:
                    raise ValueError('Answer must exactly match an option')
            else:
                if q.get('options', []) != []:
                    raise ValueError('Input must not have options')
                answers = q['answer'] if isinstance(q['answer'], list) else [q['answer']]
                if not 1 <= len(answers) <= 6:
                    raise ValueError('Input needs 1-6 accepted answers')
                for answer in answers:
                    text(answer)
                    if not normalise(answer):
                        raise ValueError('Input answer is empty after normalisation')
                if len({normalise(a) for a in answers}) != len(answers):
                    raise ValueError('Duplicate input answer aliases')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Directory containing the two pages')
    parser.add_argument('--input', type=Path, help='Validate/apply already generated JSON instead of calling Hermes')
    parser.add_argument('--output', type=Path, help='Save validated JSON for review (outside the repository)')
    parser.add_argument('--check', action='store_true', help='Generate and validate, but do not write pages')
    args = parser.parse_args()
    originals = {c: (args.root / (c + '.html')).read_bytes() for c in CHILDREN}
    previous = {c: extract_exercises(b.decode('utf-8'))[0] for c, b in originals.items()}
    batch = json.loads(args.input.read_text()) if args.input else generate_batch(previous)
    for c, before in originals.items():
        if (args.root / (c + '.html')).read_bytes() != before:
            raise ValueError('Page changed while generating: ' + c)
    updates = prepare_updates(args.root, batch)
    if args.output:
        if args.output.resolve().is_relative_to(args.root.resolve()):
            raise ValueError('--output must be outside the page repository')
        args.output.write_text(json.dumps(batch, indent=2, ensure_ascii=True) + '\n', encoding='ascii')
    if not args.check:
        publish_updates(updates)
    print('validated 20 fresh questions (10 per child); ' + ('pages unchanged' if args.check else 'pages updated'))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        main()
    except Exception:
        logging.exception('Kids exercise update failed; no Git publication performed by this generator')
        raise SystemExit(1)
