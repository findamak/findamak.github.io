"""Offline role-specific validation regressions (no issuer requests)."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts/update_etf.py'


class ETFValidationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('etf_validation_target', PATH)
        assert spec and spec.loader
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.today = self.m.datetime.now(self.m.timezone.utc).date()

    def metric(self, value, **extra):
        return dict(value=value, as_of=self.today.isoformat(),
                    basis='Issuer metric', source='https://issuer.example', **extra)

    def refresh_with(self, ticker, slot, metric):
        def fetch(t):
            pair = [self.metric(-5), self.metric(0)]
            if t == ticker:
                pair[slot] = metric
            return tuple(pair)
        with patch.object(self.m, 'publish') as publish, contextlib.redirect_stdout(io.StringIO()):
            result = self.m.refresh(Path('unused.html'), fetcher=fetch)
        return result, publish.call_args.args[1], publish.call_args.args[2]

    def test_refresh_rejects_negative_yield_for_every_ticker(self):
        for ticker in self.m.TICKERS:
            with self.subTest(ticker=ticker):
                status, results, errors = self.refresh_with(ticker, 1, self.metric(-5))
                self.assertEqual(status, 1)
                self.assertNotIn(ticker, results)
                self.assertEqual(set(errors), {ticker})

    def test_refresh_restricts_policy_to_ibtc_yield(self):
        for ticker in self.m.TICKERS:
            for slot in (0, 1):
                if (ticker, slot) == ('IBTC', 1):
                    continue
                for value in (None, 2):
                    with self.subTest(ticker=ticker, slot=slot, value=value):
                        status, results, errors = self.refresh_with(
                            ticker, slot, self.metric(value, policy=True))
                        self.assertEqual(status, 1)
                        self.assertNotIn(ticker, results)
                        self.assertEqual(set(errors), {ticker})

    def test_refresh_allows_negative_performance_zero_yield_and_ibtc_policy(self):
        policy = self.metric(None, policy=True)
        policy['as_of'] = '2025-07-04'
        status, results, errors = self.refresh_with('IBTC', 1, policy)
        self.assertEqual(status, 0)
        self.assertEqual(set(results), set(self.m.TICKERS))
        self.assertEqual(errors, {})
        self.assertTrue(all(pair[0]['value'] == -5 for pair in results.values()))
        self.assertIsNone(results['IBTC'][1]['value'])

    def test_missing_numeric_without_policy_is_rejected_in_both_slots(self):
        for slot in (0, 1):
            with self.subTest(slot=slot):
                status, results, errors = self.refresh_with('IBTC', slot, self.metric(None))
                self.assertEqual(status, 1)
                self.assertNotIn('IBTC', results)
                self.assertEqual(set(errors), {'IBTC'})

    def test_policy_cannot_bypass_validation_without_explicit_ibtc_yield_context(self):
        with self.assertRaises(ValueError):
            self.m.validate_metric(self.metric(None, policy=True), date=self.today)


if __name__ == '__main__':
    unittest.main()
