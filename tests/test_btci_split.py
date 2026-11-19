"""Regression for Yahoo's delayed BITO reverse-split adjustment."""
import copy
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('btci', Path(__file__).resolve().parents[1] / 'scripts/update_btci.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def ts(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())

def fixture():
    return {'chart': {'result': [{'timestamp': [ts('2024-10-17'), ts('2026-11-18'), ts('2026-11-19')],
        'meta': {}, 'events': {'dividends': {'old': {'date': ts('2026-11-02'), 'amount': .015}}},
        'indicators': {'quote': [{'close': [19.01, 8.31, 16.48]}],
                       'adjclose': [{'adjclose': [9.843086242675781, 8.31, 16.48]}]}}]}}

class SplitTests(unittest.TestCase):
    def test_lagging_history_return(self):
        with patch.object(m, '_get_json', return_value=fixture()):
            df, meta = m.download_yahoo_history('BITO', 'bito')
        self.assertAlmostEqual((df.iloc[-1].bito_close / df.iloc[0].bito_close - 1)*100, -16.2864201, places=5)
        self.assertAlmostEqual(df.iloc[1].bito_raw_close, 16.62)
        self.assertAlmostEqual(meta['events']['dividends']['old']['amount'], .03)

    def test_already_adjusted_history_is_unchanged(self):
        payload = fixture()
        r = payload['chart']['result'][0]
        for values in [r['indicators']['quote'][0]['close'], r['indicators']['adjclose'][0]['adjclose']]:
            values[:2] = [v * 2 for v in values[:2]]
        r['events']['dividends']['old']['amount'] *= 2
        original = copy.deepcopy(payload)
        with patch.object(m, '_get_json', return_value=payload):
            df, _ = m.download_yahoo_history('BITO', 'bito')
        self.assertEqual(payload, original)
        self.assertAlmostEqual(df.iloc[-1].bito_close / df.iloc[0].bito_close, 16.48 / (9.843086242675781 * 2))

    def test_ambiguous_boundary_is_rejected(self):
        payload = fixture()
        payload['chart']['result'][0]['indicators']['quote'][0]['close'][-1] = 40
        with patch.object(m, '_get_json', return_value=payload):
            with self.assertRaises(RuntimeError):
                m.download_yahoo_history('BITO', 'bito')

    def test_repair_is_idempotent(self):
        r = fixture()['chart']['result'][0]
        m.repair_bito_split(r)
        repaired = copy.deepcopy(r)
        m.repair_bito_split(r)
        self.assertEqual(r, repaired)

if __name__ == '__main__':
    unittest.main()
