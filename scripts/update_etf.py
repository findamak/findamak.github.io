#!/usr/bin/env python3
"""Refresh only ETF performance/yield from issuer sources; fail closed per metric."""
from datetime import datetime, date, timezone
import re
import math
import os
import json
import html
import tempfile
from pathlib import Path
import argparse
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

AU_BASE = 'https://www.vanguard.com.au/personal/api/products/personal/'
AU_PORTS = {'VTS': '0970', 'VAS': '8205', 'VEU': '0991', 'VGS': '8212'}
GS_URL = 'https://am.gs.com/services/funds'
GS_QUERY = 'query getFundsDetail($fundDetailRequest: FundDetailRequest) { fundsDetail(fundDetailRequest: $fundDetailRequest) { ticker averageAnnualizedReturns averageAnnualizedReturnsAsAtDate yield { label value asAtDate } } }'


def request(url, payload=None):
    # Issuers reject the default urllib TLS fingerprint. This is their public
    # website data, fetched with browser-compatible TLS, not a proxy or login.
    from curl_cffi import requests
    for attempt in range(3):
        try:
            response = requests.request('POST' if payload else 'GET', url, json=payload, impersonate='chrome', timeout=45)
            response.raise_for_status()
            if not response.content:
                raise ValueError('Empty response')
            return response
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def text_page(url):
    from bs4 import BeautifulSoup
    return BeautifulSoup(request(url).text, 'html.parser').get_text(' ', strip=True)


def pdf_text(url):
    body = request(url).content
    if not body.startswith(b'%PDF'):
        raise ValueError('Issuer document is not a PDF')
    executable = shutil.which('pdftotext') or '/home/linuxbrew/.linuxbrew/bin/pdftotext'
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'issuer.pdf'
        path.write_bytes(body)
        result = subprocess.run([executable, '-layout', str(path), '-'], capture_output=True, text=True, check=True, timeout=45)
    return ' '.join(result.stdout.split())


def parse_ibtc_policy(text, url):
    match(r'In the normal course Holders should not expect to receive any distributions of ordinary income', text)
    stamp = match(r'Product Disclosure Statement\s+(\d+ \w+ \d{4})\s*\|', text)[1]
    return dict(value=None, as_of=source_date(stamp), basis='No ordinary income distributions expected; PDS policy, not measured trailing yield', source=url, policy=True)


def fetch_fund(ticker):
    if ticker in ('VT', 'VTI'):
        url = 'https://investor.vanguard.com/irr/funds/profile/' + {'VT': '3141', 'VTI': '0970'}[ticker]
        return parse_us(request(url).json(), ticker, url)
    if ticker in AU_PORTS:
        port = AU_PORTS[ticker]
        url = AU_BASE + 'funds/etf'
        p = parse_au_performance(request(url).json(), port, url)
        url = AU_BASE + 'fund/' + port + '/overview'
        return p, parse_au_yield(request(url).json(), port, url)
    if ticker in ('QQQI', 'BTCI'):
        url = 'https://neosfunds.com/' + ticker.lower() + '/'
        return parse_neos(text_page(url), url)
    if ticker == 'GPIX':
        payload = {'query': GS_QUERY, 'variables': {'fundDetailRequest': {'country': 'us', 'language': 'en', 'audience': 'advisors', 'pvNumber': 'PV105258', 'shareClassId': '38149W622'}}}
        return parse_gs(request(GS_URL, payload).json(), 'https://am.gs.com/en-us/advisors/funds/detail/PV105258/38149W622/goldman-sachs-s-p-500-premium-income-etf')
    if ticker == 'NDQ':
        url = 'https://www.betashares.com.au/fund/nasdaq-100-etf/'
        return parse_ndq(text_page(url), url)
    if ticker == 'IVV':
        url = 'https://www.blackrock.com/au/products/275304/ishares-s-p-500-etf'
        return parse_ivv(text_page(url), url)
    if ticker == 'IBTC':
        url = 'https://www.monochrome.au/files/monochrome-bitcoin-etf-fund-factsheet'
        p = parse_ibtc_performance(pdf_text(url), url)
        url = 'https://www.monochrome.au/files/monochrome-bitcoin-etf-product-disclosure-statement'
        return p, parse_ibtc_policy(pdf_text(url), url)
    raise ValueError('Unknown ticker: ' + ticker)


def refresh(path, fetcher=None):
    results, errors = {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(fetcher or fetch_fund, ticker): ticker for ticker in TICKERS}
        for job in as_completed(jobs):
            ticker = jobs[job]
            try:
                pair = job.result()
                if len(pair) != 2:
                    raise ValueError('Expected performance and yield')
                for role, m in zip(('performance', 'yield'), pair):
                    validate_metric(m, ticker=ticker, role=role)
                results[ticker] = pair
                print(json.dumps({'ticker': ticker, 'metrics': pair}), flush=True)
            except Exception as exc:
                errors[ticker] = str(exc)
                print(json.dumps({'ticker': ticker, 'error': str(exc)}), flush=True)
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    publish(path, results, errors, now)
    print(json.dumps({'verified_etfs': len(results), 'required_etfs': len(TICKERS), 'published': not bool(errors), 'errors': errors}), flush=True)
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', type=Path, default=Path(__file__).resolve().parents[1] / 'etf.html')
    args = parser.parse_args()
    return refresh(args.page)


TICKERS = ('VT', 'VTI', 'GPIX', 'QQQI', 'BTCI', 'VTS', 'IVV', 'NDQ', 'VAS', 'VEU', 'IBTC', 'VGS')


def validate_metric(m, date=None, *, ticker=None, role='performance'):
    if m.get('policy') and (ticker != 'IBTC' or role != 'yield'):
        raise ValueError('Distribution policy is only valid for IBTC yield')
    today = date or datetime.now(timezone.utc).date()
    age = (today - globals()['date'].fromisoformat(m['as_of'])).days
    if age < 0 or (not m.get('policy') and age > (10 if 'Calculated trailing' in m['basis'] else 120)):
        raise ValueError('Issuer data stale or future-dated: ' + m['as_of'])
    if m['value'] is None:
        if not m.get('policy'):
            raise ValueError('Missing numeric metric without verified policy')
    elif not math.isfinite(m['value']) or not (0 if role == 'yield' else -100) <= m['value'] <= 1000:
        raise ValueError('Invalid numeric metric')


def publish(path, results, errors, now):
    """All metrics change together, or none do. Failure changes status only."""
    original = path.read_text()
    document = original
    previous = re.search(r'data-etf-last-success="([^"]*)"', original)
    last = previous[1] if previous else 'Not yet verified'
    if not errors:
        if set(results) != set(TICKERS):
            raise ValueError('Publication requires exactly 12 ETFs')
        seen = []
        def update_row(found):
            row = found[0]
            ticker_match = re.search(r'class="ticker">([^<]+)', row)
            if not ticker_match:
                return row
            ticker = ticker_match[1]
            if ticker not in results or ticker in seen:
                raise ValueError('Unexpected or duplicate ticker: ' + ticker)
            seen.append(ticker)
            cells = list(re.finditer(r'<td\b.*?</td>', row, re.S))
            if len(cells) != 8:
                raise ValueError('ETF table schema changed')
            for index, m in reversed(list(zip((4, 5), results[ticker]))):
                value = m['value']
                label = 'N/A' if value is None else f'{value:.2f}%'
                color = 'zero' if value is None or value == 0 else ('positive' if value > 0 else 'negative')
                detail = f"{m['basis']}; {'PDS dated' if m.get('policy') else 'as of'} {m['as_of']}"
                cell = f'<td class="metric {color}">{label}<small data-etf-basis="true" style="display:block;white-space:normal;min-width:220px;font-weight:400;color:var(--muted)"><a class="source-link" href="{html.escape(m["source"], quote=True)}" rel="noopener" target="_blank">{html.escape(detail)}</a></small></td>'
                c = cells[index]
                row = row[:c.start()] + cell + row[c.end():]
            return row
        document = re.sub(r'<tr>.*?</tr>', update_row, document, flags=re.S)
        if set(seen) != set(TICKERS):
            raise ValueError('Page is missing ETF rows')
        ranking = sorted((results[t][0]['value'], t) for t in TICKERS)
        for title, (v, t) in [('Top listed performance', ranking[-1]), ('Lowest listed performance', ranking[0])]:
            document, n = re.subn(r'(<span class="label">' + title + r'</span><span class="value">).*?(</span>)', lambda x: x[1] + f'{t} {v:.2f}%' + x[2], document)
            if n != 1:
                raise ValueError('Missing summary ranking')
        last = now
    status = ('STALE / ERROR — all prior figures retained. Failed: ' + ', '.join(sorted(errors))) if errors else '12/12 ETFs verified; 23 numeric metrics + IBTC distribution policy'
    from zoneinfo import ZoneInfo
    display = datetime.fromisoformat(last).astimezone(ZoneInfo('Australia/Sydney')).strftime('%d %b %Y, %H:%M %Z') if last != 'Not yet verified' else last
    if errors:
        display += ' — STALE / ERROR'
    summary = f'<div class="summary-item" id="etf-last-updated" data-etf-last-success="{html.escape(last)}"><span class="label">Last updated</span><span class="value" style="font-size:0.82rem">{html.escape(display)}</span></div>'
    status_note = f'<p class="note" id="etf-refresh-status">{html.escape(status)}. Last successful refresh: {html.escape(last)}. Last attempt: {html.escape(now)}. Refresh time is not the issuer valuation date; source dates and yield definitions appear beside each figure. Performance periods and currencies differ; figures are not directly comparable. AUM and inception-date columns are not refreshed by this job.</p>'
    if 'id="etf-refresh-status"' in document:
        document = re.sub(r'<p class="note" id="etf-refresh-status".*?</p>', lambda _: status_note, document, flags=re.S)
    else:
        document = document.replace('  </main>', '    ' + status_note + '\n  </main>')
    if 'id="etf-last-updated"' in document:
        document, n = re.subn(r'<div class="summary-item" id="etf-last-updated".*?</div>', lambda _: summary, document, flags=re.S)
        if n != 1:
            raise ValueError('Duplicate refresh summary')
    else:
        document, n = re.subn(r'(\s*</aside>)', lambda x: '\n        ' + summary + x[0], document, count=1)
        if n != 1:
            raise ValueError('Missing summary box')
    # One file means figures and status cannot be torn across a multi-file write.
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False, encoding='utf-8') as f:
        temp = Path(f.name)
        try:
            f.write(document)
            f.flush()
            os.fsync(f.fileno())
            os.chmod(temp, path.stat().st_mode & 0o777)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)



def one(items):
    items = list(items)
    if len(items) != 1:
        raise ValueError('Expected exactly one issuer record, got ' + str(len(items)))
    return items[0]


def trailing_yield(rows, nav, as_of):
    end = date.fromisoformat(as_of)
    try:
        start = end.replace(year=end.year - 1)
    except ValueError:
        start = end.replace(year=end.year - 1, day=28)
    dates = [date.fromisoformat(d) for d, _ in rows]
    if len(set(dates)) != len(dates) or not dates or min(dates) > start:
        raise ValueError('Incomplete or duplicate distribution history')
    selected = [float(v) for d, v in rows if start < date.fromisoformat(d) <= end]
    if len(selected) < 4 or not math.isfinite(float(nav)) or float(nav) <= 0:
        raise ValueError('Incomplete quarterly distribution window or invalid NAV')
    if any(not math.isfinite(v) or v < 0 for v in selected):
        raise ValueError('Invalid distribution')
    return sum(selected) / float(nav) * 100


def parse_au_yield(payload, port, url):
    d = one(x for x in payload['data'] if x['portId'] == port)
    nav = max(d['navPrices'], key=lambda x: x['asOfDate'])
    code = 'INC' if port in ('0970', '0991') else 'CASH'
    rows = []
    for x in d['periodicDistributions']:
        cash = one(t for t in x['taxDetails'] if t['distributionType']['distCode'] == code)
        if cash['currencyCode'] != nav['currencyCode']:
            raise ValueError('NAV/distribution currency mismatch')
        rows.append((x['exDividendDate'], cash['distributionAmount']))
    basis = 'Calculated trailing 12-month cash distributions / NAV (' + nav['currencyCode'] + '); ex-date window'
    if code == 'INC':
        basis += '; underlying US fund, not AUD ASX yield'
    return metric(trailing_yield(rows, nav['price'], nav['asOfDate']), nav['asOfDate'], basis, url)


def parse_au_performance(payload, port, url):
    d = one(x for x in payload['data'] if x['portId'] == port)
    p = one(x for x in d['totalReturns'] if x['returnType'] == 'ANNL' and x['returnPeriod'] == 'ITD')
    return metric(p['percent'], p['effectiveDate'], 'Issuer Australian-site total return p.a. (AUD); issuer inception series', url)


def parse_us(payload, ticker, url):
    dash = payload['dashboard']
    if dash['ticker'] != ticker:
        raise ValueError('Wrong Vanguard ticker')
    p = payload['performancefees']['totalReturns']['summary']['monthEnd']
    rows = [(source_date(x['recordDate']), float(x['share'].replace('$', '').replace(',', ''))) for x in payload['distributions']['incomeCapitalGains'] if x['type'] == 'Dividend']
    nav = float(dash['navPrice'].replace('$', '').replace(',', ''))
    stamp = source_date(dash['navPriceAsOfDate'])
    return (metric(p['fundReturn']['sinceInceptionPct'], p['asOfDate'], 'NAV total return p.a. (USD)', url),
            metric(trailing_yield(rows, nav, stamp), stamp, 'Calculated trailing 12-month dividends / NAV (USD); record-date window', url))


def match(pattern, text):
    found = re.search(pattern, text, re.I | re.S)
    if not found:
        raise ValueError('Issuer schema changed: ' + pattern[:100])
    return found


def source_date(value):
    value = value.replace('Sept', 'Sep').strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d-%b-%Y', '%d %B %Y'):
        try:
            return datetime.strptime(value[:10] if fmt == '%Y-%m-%d' else value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError('Unrecognised issuer date: ' + value)


def metric(value, as_of, basis, url):
    return dict(value=float(str(value).replace('%', '')), as_of=source_date(as_of), basis=basis, source=url)


def parse_gs(payload, url):
    d = payload['data']['fundsDetail']
    if d['ticker'] != 'GPIX':
        raise ValueError('Wrong GS share class')
    p = next(x for x in d['averageAnnualizedReturns'] if x['id'] == 'nav')
    y = next(x for x in d['yield'] if x['label'] == 'twelveMthTrailingYield')
    return (metric(p['sinceInception'], d['averageAnnualizedReturnsAsAtDate'], 'NAV total return p.a. (USD)', url),
            metric(y['value'], y['asAtDate'], '12-month trailing yield', url))


def parse_ndq(text, url):
    p = match(r'Since inception p\.a\.\s+([-\d.]+)%.*?As at (\d+ \w+ \d{4})', text)
    y = match(r'12 mth distribution yield\*?\s+([-\d.]+)%\s*\*?As at (\d+ \w+ \d{4})', text)
    return (metric(p[1], p[2], 'NAV total return p.a. (AUD)', url),
            metric(y[1], y[2], '12-month distribution yield', url))


def parse_ivv(text, url):
    p = match(r'Returns Average Annual Cumulative Calendar Year as of (\d+-\w+-\d{4}).*?1y 3y 5y 10y Incept\. Total Return \(%\)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', text)
    y = match(r'12m Trailing Yield as of (\d+-\w+-\d{4})\s+([-\d.]+)%', text)
    return (metric(p[6], p[1], 'NAV total return p.a. (AUD); issuer series includes pre-redomiciliation history', url),
            metric(y[2], y[1], '12-month trailing yield', url))


def parse_ibtc_performance(text, url):
    p = match(r'PERFORMANCE % AS AT (\d+/\d+/\d+).*?Inception p\.a\..*?IBTC2\s+((?:[-\d.]+%\s*){6})', text)
    stamp = datetime.strptime(p[1], '%d/%m/%Y').date().isoformat()
    return metric(p[2].split()[5], stamp, 'Since inception p.a. (AUD), net of fees/costs before tax; issuer factsheet', url)


def parse_neos(text, url):
    m = match(r'Data as of:\s*([\d/]+)\s*Spacer column 1 Mo 3 Mo 6 Mo YTD Inception \(Cumulative\) 1 Yr 3 Yr 5 Yr Inception \(Annualized\).*?NAV Performance\s+(.*?)\s+Market Performance', text)
    values = m[2].split()
    if len(values) != 9:
        raise ValueError('NEOS performance column count changed')
    y = match(r'Distribution Information \(as of ([\d/]+)\).*?12-Month Trailing Distribution Rate\s+([-\d.]+)%', text)
    return (metric(values[8], m[1], 'NAV total return p.a. (USD)', url),
            metric(y[2], y[1], '12-month trailing distribution rate; may include return of capital', url))


if __name__ == '__main__':
    raise SystemExit(main())
