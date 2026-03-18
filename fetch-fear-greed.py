#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

OUTPUT_FILE = Path('/home/amak/findamak.github.io/fear-greed.json')
COINS = {
    'bitcoin': 'btc',
    'ethereum': 'eth',
}


def fetch_cfgi(symbol: str):
    url = f'https://www.cfgi.io/{symbol}-fear-greed-index/'
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    html = resp.text

    # Value for "Now"
    value_match = re.search(r'Now</h5>[\s\S]{0,700}?value__score[^>]*>(\d+)<', html, re.IGNORECASE)
    label_match = re.search(r'Now</h5>[\s\S]{0,700}?value__label[^>]*>([^<]+)<', html, re.IGNORECASE)

    if not value_match:
        # fallback to first visible score in page
        value_match = re.search(r'value__score[^>]*>(\d+)<', html, re.IGNORECASE)

    if not value_match:
        raise ValueError(f'Could not parse CFGI value for {symbol}')

    value = int(value_match.group(1))
    label = label_match.group(1).strip() if label_match else classify(value)

    return {
        'value': value,
        'classification': label,
        'source': url,
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


def main():
    result = {
        'lastUpdated': datetime.now(timezone.utc).isoformat(),
        'indices': {}
    }

    for full_name, short in COINS.items():
        result['indices'][short] = fetch_cfgi(full_name)

    OUTPUT_FILE.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'✓ Fear & Greed updated: {datetime.now().strftime("%a %d %b %Y %H:%M:%S %Z") or "local"}')
    print(f'  Output: {OUTPUT_FILE}')
    print(f"  BTC: {result['indices']['btc']['value']} ({result['indices']['btc']['classification']})")
    print(f"  ETH: {result['indices']['eth']['value']} ({result['indices']['eth']['classification']})")


if __name__ == '__main__':
    main()
