"""Exercise the real cron wrapper against a disposable local Git remote."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).resolve().parents[1] / 'scripts/update_fear_greed_and_push.sh'


class CronTests(unittest.TestCase):
    def test_shared_checkout_preserves_unrelated_staged_work(self):
        self.assertTrue(WRAPPER.exists(), 'Cron needs a locked, file-scoped publisher')
        self.assertIn('FGI_REPO_DIR', WRAPPER.read_text(), 'Do not diverge from the stock publisher checkout')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, seed = root / 'remote.git', root / 'seed'
            def git(*args, cwd=None):
                return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.STDOUT, text=True)
            git('init', '--bare', '--initial-branch=main', str(remote))
            git('init', '--initial-branch=main', str(seed))
            git('config', 'user.name', 'Test', cwd=seed)
            git('config', 'user.email', 'test@example.invalid', cwd=seed)
            # Test-only data; this remote never leaves the temporary directory.
            (seed / 'fetch-fear-greed.py').write_text("from pathlib import Path\nPath('fear-greed.json').write_text('{\"test\": true}\\n')\n")
            git('add', 'fetch-fear-greed.py', cwd=seed)
            git('commit', '-m', 'fixture', cwd=seed)
            git('remote', 'add', 'origin', str(remote), cwd=seed)
            git('push', 'origin', 'main', cwd=seed)
            (seed / 'unrelated.txt').write_text('leave staged work alone')
            git('add', 'unrelated.txt', cwd=seed)
            before = git('status', '--porcelain', cwd=seed)
            env = dict(os.environ, FGI_REPO_DIR=str(seed), FGI_STATE_DIR=str(root / 'state'),
                       GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                       GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')
            for _ in range(2):
                subprocess.run(['bash', str(WRAPPER)], cwd=seed, env=env, check=True, capture_output=True, text=True)
            self.assertEqual(git('status', '--porcelain', cwd=seed), before)
            self.assertEqual(json.loads(git('show', 'main:fear-greed.json', cwd=remote)), {'test': True})
            self.assertEqual(git('diff-tree', '--no-commit-id', '--name-only', '-r', 'main', cwd=remote).strip(), 'fear-greed.json')


if __name__ == '__main__':
    unittest.main()
