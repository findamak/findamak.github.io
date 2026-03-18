#!/usr/bin/env python3
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

OUTPUT_FILE = Path('/home/amak/findamak.github.io/fear-greed.json')
SOURCES = {
    'btc': 'https://nitter.net/BitcoinFear/rss',
    'eth': 'https://nitter.net/EthereumFear/rss',
}


def classify(value: int) -> str:
    if value <= 24:
        return 'Extreme Fear'
    if value <= 44:
        return 'Fear'
    if value <= 55:
        return 'Neutral'
    if value <= 74:
        return 'Greed'
    return 'Extreme Greed'


def extract_value(text: str) -> int:
    # Examples:
    # "Bitcoin Fear and Greed Index is 26 ~ Fear"
    # "Ethereum Fear and Greed Index is 49 - Neutral"
    match = re.search(r'Fear\s+and\s+Greed\s+Index\s+is\s+(\d{1,3})', text, re.IGNORECASE)
    if not match:
        raise ValueError(f'Could not parse fear/greed value from text: {text[:120]!r}')

    value = int(match.group(1))
    if value < 0 or value > 100:
        raise ValueError(f'Parsed value out of range: {value}')

    return value


def fetch_from_rss(symbol: str):
    url = SOURCES[symbol]
    resp = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    channel = root.find('channel')
    if channel is None:
        raise ValueError(f'Invalid RSS format for {symbol}')

    item = channel.find('item')
    if item is None:
        raise ValueError(f'No RSS items found for {symbol}')

    title = item.findtext('title') or ''
    description = item.findtext('description') or ''
    link = item.findtext('link') or ''
    pub_date = item.findtext('pubDate') or ''

    source_text = title if title.strip() else description
    value = extract_value(source_text)

    classification_match = re.search(
        r'Fear\s+and\s+Greed\s+Index\s+is\s+\d{1,3}\s*[~\-—]?\s*([A-Za-z ]+)',
        source_text,
        re.IGNORECASE,
    )
    classification = classification_match.group(1).strip() if classification_match else classify(value)

    return {
        'value': value,
        'classification': classification,
        'source': url,
        'sourcePost': link,
        'sourcePublishedAt': pub_date,
    }


def main():
    result = {
        'lastUpdated': datetime.now(timezone.utc).isoformat(),
        'indices': {
            'btc': fetch_from_rss('btc'),
            'eth': fetch_from_rss('eth'),
        },
    }

    OUTPUT_FILE.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')

    print(f'✓ Fear & Greed updated: {datetime.now().strftime("%a %d %b %Y %H:%M:%S %Z") or "local"}')
    print(f'  Output: {OUTPUT_FILE}')
    print(f"  BTC: {result['indices']['btc']['value']} ({result['indices']['btc']['classification']})")
    print(f"  ETH: {result['indices']['eth']['value']} ({result['indices']['eth']['classification']})")


if __name__ == '__main__':
    main()
