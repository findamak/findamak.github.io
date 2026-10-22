import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kids', ROOT / 'scripts/update_kids_exercises.py')
kids = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kids)


def candidate():
    return {child: [dict(type='choice', title='Numeracy', question='%s fresh question %s?' % (child, i),
                        prompt='Think carefully.', options=['1', '2', '3', '4'], answer='2')
                    for i in range(10)] for child in ('chiara', 'cooper')}


class ValidationTests(unittest.TestCase):
    def test_rejects_input_answers_that_normalise_to_empty(self):
        for answer in ('?', '.', '!', ' .!? ', ['?'], ['two', '.']):
            with self.subTest(answer=answer):
                data = candidate()
                data['chiara'][0].update(type='input', options=[], answer=answer)
                with self.assertRaisesRegex(ValueError, 'empty after normalisation'):
                    kids.validate_batch(data, {})

    def test_validates_complete_fresh_batch_and_rejects_invalid_data(self):
        self.assertTrue(hasattr(kids, 'validate_batch'), 'fresh batch validation is missing')
        previous = {c: [{'question': c + ' old question'}] for c in candidate()}
        kids.validate_batch(candidate(), previous)
        cases = []
        def bad(change):
            data = candidate()
            change(data)
            cases.append(data)
        bad(lambda d: d.pop('cooper'))
        bad(lambda d: d['chiara'].pop())
        bad(lambda d: d['chiara'][0].update(question='chiara old question!'))
        bad(lambda d: d['chiara'][1].update(question=d['chiara'][0]['question']))
        bad(lambda d: d['chiara'][0].update(options=['1','1','3','4']))
        bad(lambda d: d['chiara'][0].update(options=['Yes.', 'yes!', '3', '4']))
        bad(lambda d: d['chiara'][0].update(answer='5'))
        bad(lambda d: d['chiara'][0].update(title='caf\u00e9'))
        bad(lambda d: d['chiara'][0].update(question='</script><script>alert(1)</script>'))
        bad(lambda d: d['chiara'][0].update(type='unknown'))
        bad(lambda d: d['chiara'][0].update(extra='no'))
        bad(lambda d: d['chiara'][0].update(prompt=''))
        bad(lambda d: d['chiara'][0].update(type='input', options=[], answer=[]))
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                kids.validate_batch(data, previous)
        data = candidate()
        data['cooper'][0].update(type='input', options=[], answer=['two', '2'])
        kids.validate_batch(data, previous)


class PublishingTests(unittest.TestCase):
    def test_prepare_validates_both_pages_before_writing_and_preserves_html(self):
        self.assertTrue(hasattr(kids, 'prepare_updates'), 'validated publisher is missing')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = {c: [{'question': c + ' old question'}] for c in candidate()}
            for c in old:
                (root / (c + '.html')).write_text('prefix var exercises = ' + json.dumps(old[c]) + '; suffix')
            before = {c: (root / (c + '.html')).read_bytes() for c in old}
            data = candidate()
            data['chiara'][0]['prompt'] = r'A backslash \\ and literal \\n are safe.'
            updates = kids.prepare_updates(root, data)
            self.assertEqual(before, {c: (root / (c + '.html')).read_bytes() for c in old})
            kids.publish_updates(updates)
            for c in old:
                html = (root / (c + '.html')).read_text()
                self.assertEqual(kids.extract_exercises(html)[0], data[c])
                self.assertTrue(html.startswith('prefix var exercises = '))
                self.assertTrue(html.endswith('; suffix'))
            # A broken second page cannot partially overwrite the first.
            (root / 'cooper.html').write_text('no marker')
            first = (root / 'chiara.html').read_bytes()
            with self.assertRaises(ValueError):
                kids.prepare_updates(root, candidate())
            self.assertEqual((root / 'chiara.html').read_bytes(), first)
            with self.assertRaises(ValueError):
                kids.extract_exercises('var exercises = []; var exercises = [];')


class ProgressTests(unittest.TestCase):
    def test_progress_key_changes_only_when_exercises_change(self):
        import subprocess
        for child in ('chiara', 'cooper'):
            html = (ROOT / (child + '.html')).read_text()
            script = html.split('(function () {', 1)[1].split('var answered =', 1)[0]
            program = ('var pageId = "test"; var exercises = [{question: "first"}];' + script
                       + 'var first = storageKey;' + script
                       + 'if (first !== storageKey) throw Error("unstable key");'
                       + 'exercises = [{question: "second"}];' + script
                       + 'if (first === storageKey) throw Error("stale progress retained");')
            result = subprocess.run(['node', '-e', program], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class GenerationTests(unittest.TestCase):
    def test_tool_free_generation_uses_sparse_env_and_reports_failure(self):
        self.assertTrue(hasattr(kids, 'generate_batch'), 'AI generation is missing')
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / 'fake-hermes'
            # Deliberate test double, never used for real generation evidence.
            script.write_text('#!/usr/bin/python3\nimport os,sys,json\n'
                              'assert os.environ["HERMES_HOME"] == "/home/amak/.hermes"\n'
                              'assert "--ignore-rules" in sys.argv\n'
                              'assert sys.argv[sys.argv.index("--toolsets")+1] == "context_engine"\n'
                              'print(' + repr(json.dumps(candidate())) + ')\n')
            script.chmod(0o700)
            self.assertEqual(kids.generate_batch({}, executable=str(script), timeout=5), candidate())
            script.write_text('#!/bin/sh\necho real-provider-error >&2\nexit 7\n')
            with self.assertLogs(level='WARNING') as logs:
                with self.assertRaisesRegex(RuntimeError, 'real-provider-error'):
                    kids.generate_batch({}, executable=str(script), timeout=5)
            self.assertIn('real-provider-error', logs.output[0])
            script.write_text('#!/bin/sh\nsleep 5\n')
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                kids.generate_batch({}, executable=str(script), timeout=0.1)


class CommandTests(unittest.TestCase):
    def test_cli_check_and_invalid_input_never_touch_pages(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for c in ('chiara', 'cooper'):
                (root / (c + '.html')).write_text('var exercises = ' + json.dumps([{'question': c + ' old'}]) + ';')
            source = root / 'input.json'
            source.write_text(json.dumps(candidate()))
            command = ['/usr/bin/python3', str(ROOT / 'scripts/update_kids_exercises.py'),
                       '--root', tmp, '--input', str(source)]
            before = {p: p.read_bytes() for p in root.glob('*.html')}
            result = subprocess.run(command + ['--check'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('validated 20 fresh questions', result.stdout)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            source.write_text('{}')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            source.write_text(json.dumps(candidate()))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(before, {p: p.read_bytes() for p in before})


class WrapperTests(unittest.TestCase):
    def test_publisher_isolates_git_and_refuses_dirty_or_wrong_branch(self):
        import subprocess
        wrapper = (ROOT / 'scripts/update_kids_exercises_and_push.sh').read_text()
        self.assertIn('git worktree add --detach', wrapper, 'isolated publisher is missing')
        def run(*args, cwd):
            return subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            remote = Path(tmp) / 'remote.git'
            run('git', 'init', '--bare', str(remote), cwd=root).check_returncode()
            run('git', 'init', '-b', 'main', cwd=root).check_returncode()
            (root / 'scripts').mkdir()
            entry = root / 'scripts/update_kids_exercises_and_push.sh'
            entry.write_text(wrapper)
            # Git integration fixture: generator is separately tested with real AI.
            (root / 'scripts/update_kids_exercises.py').write_text(
                'from pathlib import Path\nfor c in ("chiara", "cooper"):\n Path(c+".html").write_text("new content")\n')
            for c in ('chiara', 'cooper'):
                (root / (c + '.html')).write_text('old content')
            run('git', 'add', '.', cwd=root).check_returncode()
            run('git', '-c', 'user.name=Test', '-c', 'user.email=test@example.org', 'commit', '-m', 'base', cwd=root).check_returncode()
            run('git', 'remote', 'add', 'origin', str(remote), cwd=root).check_returncode()
            run('git', 'push', 'origin', 'main', cwd=root).check_returncode()
            original = run('git', 'rev-parse', 'HEAD', cwd=root).stdout.strip()
            result = run('bash', str(entry), cwd=root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(run('git', 'rev-parse', 'HEAD', cwd=root).stdout.strip(), original)
            self.assertEqual(run('git', 'status', '--porcelain', cwd=root).stdout, '')
            published = run('git', '--git-dir=' + str(remote), 'show', 'main:chiara.html', cwd=root)
            self.assertEqual(published.stdout, 'new content')
            for staged in (False, True):
                (root / 'unrelated.txt').write_text('must not commit')
                if staged:
                    run('git', 'add', 'unrelated.txt', cwd=root)
                result = run('bash', str(entry), cwd=root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('dirty', result.stderr)
            run('git', 'reset', '--', 'unrelated.txt', cwd=root)
            (root / 'unrelated.txt').unlink()
            run('git', 'checkout', '-b', 'not-main', cwd=root)
            result = run('bash', str(entry), cwd=root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('main', result.stderr)


class CompatibilityTests(unittest.TestCase):
    def test_checks_executable_code_not_words_inside_exercise_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for c in ('chiara', 'cooper'):
                (root / (c + '.html')).write_text('<script>var exercises = ' + json.dumps([{'question': c + ' old'}]) + '; const unsafe = 1;</script>')
            data = candidate()
            data['chiara'][0]['question'] = 'Is the violet tablet on the table?'
            with self.assertRaisesRegex(ValueError, 'legacy'):
                kids.prepare_updates(root, data)
            for c in ('chiara', 'cooper'):
                p = root / (c + '.html')
                p.write_text(p.read_text().replace('const unsafe', 'var safe'))
            kids.prepare_updates(root, data)


if __name__ == '__main__':
    unittest.main()
