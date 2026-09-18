"""Offline regression tests; fixtures are small excerpts of issuer responses."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts/update_etf.py'

def module():
    spec = importlib.util.spec_from_file_location('update_etf', PATH)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class ETFTests(unittest.TestCase):
    def test_issuer_parsers_select_nav_and_p_a(self):
        m = module()
        self.assertTrue(hasattr(m, 'parse_gs'), 'additional issuer parsers missing')
        gs = {'data': {'fundsDetail': {'ticker': 'GPIX', 'averageAnnualizedReturns': [{'id': 'nav', 'sinceInception': '21.94'}, {'id': 'marketPrice', 'sinceInception': '21.97'}], 'averageAnnualizedReturnsAsAtDate': '2026-08-31', 'yield': [{'label': 'twelveMthTrailingYield', 'value': '8.05', 'asAtDate': '2026-08-31'}]}}}
        self.assertEqual(m.parse_gs(gs, 'url')[0]['value'], 21.94)
        ndq = 'Since inception p.a. 19.38% 19.78% Inception date 26-May-15 Performance (Total Return) * As at 31 August 2026. 12 mth distribution yield* 1.5% *As at 31 August 2026.'
        self.assertEqual(m.parse_ndq(ndq, 'url')[0]['value'], 19.38)
        ivv = 'Returns Average Annual Cumulative Calendar Year as of 31-Aug-2026 30-June-2026 31-Dec-2025 1y 3y 5y 10y Incept. Total Return (%) 9.66 16.76 12.96 15.65 7.46 Benchmark (%) 9.55 12m Trailing Yield as of 16-Sept-2026 1.05%'
        self.assertEqual(m.parse_ivv(ivv, 'url')[0]['value'], 7.46)
        mono = 'PERFORMANCE % AS AT 31/07/2026 Trailing Since Inception p.a. IBTC2 5.25% -14.63% -23.02% -50.58% -5.85% 38.08%'
        self.assertEqual(m.parse_ibtc_performance(mono, 'url')['value'], 38.08)
        with self.assertRaises(ValueError):
            m.parse_ibtc_performance(mono.replace('Inception p.a.', 'Inception total'), 'url')

    def test_trailing_window_and_cash_not_tax_components(self):
        m = module()
        self.assertTrue(hasattr(m, 'trailing_yield'), 'trailing calculation missing')
        rows = [('2025-09-17', 99), ('2025-09-18', 1), ('2026-01-01', 1), ('2026-04-01', 1), ('2026-07-01', 1), ('2026-09-18', 99)]
        self.assertEqual(m.trailing_yield(rows, 100, '2026-09-17'), 4)
        with self.assertRaises(ValueError):
            m.trailing_yield(rows[1:], 100, '2026-09-17')
        with self.assertRaises(ValueError):
            m.trailing_yield(rows + [rows[2]], 100, '2026-09-17')
        data = {'portId': '8205', 'navPrices': [{'price': 100, 'asOfDate': '2026-09-17', 'currencyCode': 'AUD'}], 'periodicDistributions': [
            {'exDividendDate': d, 'taxDetails': [{'distributionType': {'distCode': c}, 'distributionAmount': a, 'currencyCode': 'AUD'} for c, a in [('CASH', v), ('GRSS', 500)]]}
            for d, v in rows]}
        self.assertEqual(m.parse_au_yield({'data': [data]}, '8205', 'url')['value'], 4)

    def test_atomic_publication_and_failure_status(self):
        import tempfile
        m = module()
        self.assertTrue(hasattr(m, 'publish'), 'atomic publisher missing')
        original = (PATH.parents[1] / 'etf.html').read_text()
        good = {t: (m.metric(1, '2026-08-31', 'NAV p.a.', 'https://issuer.example'), m.metric(2, '2026-08-31', 'TTM', 'https://issuer.example')) for t in m.TICKERS}
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'etf.html'
            p.write_text(original)
            m.publish(p, good, {}, '2026-09-18T01:00:00+00:00')
            success = p.read_text()
            self.assertIn('2026-09-18T01:00:00+00:00', success)
            self.assertIn('18 Sep 2026, 11:00 AEST', success)
            self.assertIn('id="etf-refresh-status"', success)
            self.assertEqual(success.count('data-etf-basis='), 24)
            # Other columns must remain byte-for-byte unchanged.
            import re
            before = [re.findall(r'<td.*?</td>', x, re.S) for x in re.findall(r'<tr>.*?</tr>', original, re.S) if 'class="ticker"' in x]
            after = [re.findall(r'<td.*?</td>', x, re.S) for x in re.findall(r'<tr>.*?</tr>', success, re.S) if 'class="ticker"' in x]
            for b, a in zip(before, after):
                for i in (0, 1, 2, 3, 6, 7):
                    self.assertEqual(b[i], a[i])
            m.publish(p, {}, {'IBTC': 'HTTP 429'}, '2026-09-19T01:00:00+00:00')
            failed = p.read_text()
            self.assertIn('STALE / ERROR', failed)
            self.assertIn('Last successful refresh: 2026-09-18T01:00:00+00:00', failed)
            self.assertEqual(re.findall(r'<td.*?</td>', failed, re.S), re.findall(r'<td.*?</td>', success, re.S))
        with self.assertRaises(ValueError):
            m.validate_metric(m.metric(float('nan'), '2026-08-31', 'test', 'url'), date=m.date(2026, 9, 18))
        with self.assertRaises(ValueError):
            m.validate_metric(m.metric(1, '2027-08-31', 'test', 'url'), date=m.date(2026, 9, 18))

    def test_refresh_attempts_all_sources_and_returns_nonzero(self):
        import tempfile
        m = module()
        self.assertTrue(hasattr(m, 'refresh'), 'refresh orchestration missing')
        attempted = []
        def broken(ticker):
            attempted.append(ticker)
            raise RuntimeError('source unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'etf.html'
            path.write_text((PATH.parents[1] / 'etf.html').read_text())
            self.assertEqual(m.refresh(path, fetcher=broken), 1)
            self.assertEqual(set(attempted), set(m.TICKERS))
            self.assertIn('STALE / ERROR', path.read_text())
        text = 'MONOCHROME BITCOIN ETF (IBTC) Product Disclosure Statement 4 July 2025 | In the normal course Holders should not expect to receive any distributions of ordinary income.'
        self.assertIsNone(m.parse_ibtc_policy(text, 'url')['value'])
        with self.assertRaises(ValueError):
            m.parse_ibtc_policy(text.replace('not expect', 'expect'), 'url')

    def test_repeated_failure_before_first_success(self):
        import tempfile
        import re
        m = module()
        original = (PATH.parents[1] / 'etf.html').read_text()
        original = re.sub(r'<div class="summary-item" id="etf-last-updated".*?</div>', '', original)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'etf.html'
            path.write_text(original)
            m.publish(path, {}, {'VT': 'failed'}, '2026-09-18T01:00:00+00:00')
            m.publish(path, {}, {'VT': 'failed'}, '2026-09-19T01:00:00+00:00')
            self.assertIn('Not yet verified', path.read_text())

    def test_neos_annualized_not_cumulative(self):
        self.assertTrue(PATH.exists(), 'issuer updater must exist')
        spec = importlib.util.spec_from_file_location('update_etf', PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        s = 'Data as of: 08/31/2026 Spacer column 1 Mo 3 Mo 6 Mo YTD Inception (Cumulative) 1 Yr 3 Yr 5 Yr Inception (Annualized) Cumulative Annualized NAV Performance 18.63% 2.46% 15.20% -11.67% 10.70% -25.95% - - 5.58% Market Performance Distribution Information (as of 08/31/2026) 12-Month Trailing Distribution Rate 36.51%'
        p, y = m.parse_neos(s, 'https://neosfunds.com/btci/')
        self.assertEqual(p['value'], 5.58)
        self.assertEqual(y['value'], 36.51)
        self.assertEqual(p['as_of'], '2026-08-31')

if __name__ == '__main__':
    unittest.main()
