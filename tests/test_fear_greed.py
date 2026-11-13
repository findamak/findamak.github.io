"""Regression tests. CFGI sample is a reduced real 2026-11-13 response."""
import importlib.util
import json
from pathlib import Path
import unittest
from datetime import datetime, timezone
import tempfile
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('fear_greed', Path(__file__).resolve().parents[1] / 'fetch-fear-greed.py')
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)


def page(value=33, hora='2026-11-13 05:36:54', symbol='ETH'):
    props = {'cfg': {'symbol': symbol}, 'url': 'ethereum', 'initialTimeframe': '1d',
             'readings': [{'timeframe': '1d', 'current': {'value': value, 'classification': 'Fear', 'hora': hora}},
                          {'timeframe': '4h', 'current': {'value': 23, 'classification': 'Fear', 'hora': hora}}]}
    payload = '33:' + json.dumps(['$', '$L46', None, props]) + '\n'
    return '<script>self.__next_f.push(' + json.dumps([1, payload]) + ')</script>'


class SourceTests(unittest.TestCase):
    def test_daily_asset_reading_uses_source_timestamp_and_label(self):
        self.assertTrue(hasattr(fg, 'parse_cfgi'), 'Replace the dead Nitter RSS reader with CFGI per-asset readings')
        result = fg.parse_cfgi(page(), 'eth')
        self.assertEqual(result['value'], 33)
        self.assertEqual(result['classification'], 'Fear')
        self.assertEqual(result['sourcePublishedAt'], '2026-11-13T05:36:54+00:00')
        self.assertEqual(result['source'], 'https://cfgi.io/ethereum-fear-greed-index/')
        self.assertEqual(result['timeframe'], '1d')


    def test_failed_btc_does_not_block_eth_or_relabel_btc(self):
        self.assertTrue(hasattr(fg, 'refresh'), 'Fetch assets independently and retain last-known data on failure')
        old = {'value': 62, 'sourcePublishedAt': '2026-08-20T01:00:08+00:00'}
        fresh = fg.parse_cfgi(page(), 'eth')
        fetcher = Mock(side_effect=[RuntimeError('source offline'), fresh])
        result = fg.refresh({'indices': {'btc': old}}, datetime(2026, 11, 13, 6, tzinfo=timezone.utc), fetcher)
        self.assertEqual(result['indices']['btc']['value'], 62)
        self.assertEqual(result['indices']['btc']['sourcePublishedAt'], old['sourcePublishedAt'])
        self.assertEqual(result['indices']['btc']['status'], 'error')
        self.assertEqual(result['indices']['eth']['value'], 33)
        self.assertEqual(result['indices']['eth']['status'], 'ok')
        self.assertEqual(fetcher.call_count, 2)


    def test_stale_and_future_source_times_are_not_fresh(self):
        for timestamp, expected in [('2026-08-20 01:00:08', 'stale'), ('2027-01-01 00:00:00', 'error')]:
            with self.subTest(timestamp=timestamp):
                result = fg.refresh({}, datetime(2026, 11, 13, 6, tzinfo=timezone.utc),
                                    lambda symbol: fg.parse_cfgi(page(hora=timestamp, symbol=symbol.upper()), symbol))
                self.assertEqual(result['indices']['eth']['status'], expected)

    def test_invalid_or_wrong_asset_payload_is_rejected(self):
        for html in [page(value=101), page(value=True), page(symbol='BTC'), page(hora='unknown'), '<html>unavailable</html>']:
            with self.subTest(html=html[:50]):
                with self.assertRaises(ValueError):
                    fg.parse_cfgi(html, 'eth')


    def test_generator_does_not_commit_from_shared_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'fear-greed.json'
            result = {'indices': {'btc': {'value': 23, 'status': 'ok'}, 'eth': {'value': 33, 'status': 'ok'}}}
            with patch.object(fg, 'OUTPUT_FILE', output), patch.object(fg, 'refresh', return_value=result), patch('subprocess.run') as run:
                fg.main()
                self.assertEqual(json.loads(output.read_text()), result)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
