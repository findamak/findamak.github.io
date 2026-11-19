import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('update_btci', Path(__file__).resolve().parents[1] / 'scripts/update_btci.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class AumTests(unittest.TestCase):
    def test_net_assets(self):
        self.assertEqual(m.parse_net_assets('<td>Net Assets</td><td>$1,085,389,587</td>'), 1085389587)
        self.assertEqual(m.parse_net_assets('<span>Net Assets</span> <b>$1,161,052,307</b>'), 1161052307)
    def test_missing_is_not_zero(self):
        with self.assertRaises(ValueError):
            m.parse_net_assets('<p>No fund data</p>')

if __name__ == '__main__':
    unittest.main()
