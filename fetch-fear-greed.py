#!/usr/bin/env python3
"""Fetch the asset-specific CFGI daily readings (not a shared crypto index)."""
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests

REPO_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = REPO_DIR / 'fear-greed.json'
SOURCES = {
    'btc': 'https://cfgi.io/bitcoin-fear-greed-index/',
    'eth': 'https://cfgi.io/ethereum-fear-greed-index/',
}


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.inside = tag == 'script'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


def parse_cfgi(html, symbol):
    """Read source-provided 1D value, classification and UTC observation time.

    CFGI embeds these together in Next.js flight JSON. Decode JSON, never
    evaluate JavaScript or scrape an unrelated number from page prose.
    """
    parser = Scripts()
    parser.feed(html)
    chunks = []
    for script in parser.parts:
        if script.startswith('self.__next_f.push('):
            payload = json.JSONDecoder().raw_decode(script[len('self.__next_f.push('):])[0]
            if len(payload) == 2 and payload[0] == 1 and isinstance(payload[1], str):
                chunks.append(payload[1])
    for line in ''.join(chunks).splitlines():
        if not re.match(r'^[0-9a-f]+:\[', line):
            continue
        node = json.loads(line.split(':', 1)[1])
        if not isinstance(node, list) or len(node) != 4 or not isinstance(node[3], dict):
            continue
        props = node[3]
        if props.get('cfg', {}).get('symbol') != symbol.upper() or 'readings' not in props:
            continue
        current = next(r['current'] for r in props['readings'] if r['timeframe'] == '1d')
        value = current['value']
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError('Invalid CFGI value')
        label = current['classification']
        if label not in {'Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'}:
            raise ValueError('Invalid CFGI classification')
        published = datetime.strptime(current['hora'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return {'value': value, 'classification': label, 'source': SOURCES[symbol],
                'sourceName': 'CFGI', 'timeframe': '1d',
                'sourcePublishedAt': published.isoformat()}
    raise ValueError(f'No CFGI daily reading for {symbol}')


def fetch_index(symbol):
    response = requests.get(SOURCES[symbol], timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    return parse_cfgi(response.text, symbol)


def refresh(previous, now, fetcher=fetch_index):
    result = {'lastUpdated': now.isoformat(), 'indices': {}}
    for symbol in SOURCES:
        try:
            entry = fetcher(symbol)
            age = (now - datetime.fromisoformat(entry['sourcePublishedAt'])).total_seconds()
            if age < -300:
                raise ValueError('Source timestamp is in the future')
            entry['status'] = 'stale' if age > 3 * 3600 else 'ok'
        except Exception as exc:
            print(f'{symbol.upper()} fetch failed: {exc}', flush=True)
            entry = dict(previous.get('indices', {}).get(symbol, {}))
            entry['status'] = 'error'
        entry['lastCheckedAt'] = now.isoformat()
        result['indices'][symbol] = entry
    return result


def main():
    previous = json.loads(OUTPUT_FILE.read_text()) if OUTPUT_FILE.exists() else {}
    result = refresh(previous, datetime.now(timezone.utc))
    temporary = OUTPUT_FILE.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    temporary.replace(OUTPUT_FILE)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if all(entry['status'] == 'ok' for entry in result['indices'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
