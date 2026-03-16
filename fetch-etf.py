#!/usr/bin/env python3
"""
Fetch Bitcoin ETF holdings data from walletpilot.com
Run daily at 6am via cron to update etf-data.json
"""

import json
from datetime import datetime
import subprocess
import os
import re
from bs4 import BeautifulSoup

def fetch_etf_data():
    """Fetch ETF data from walletpilot"""
    url = "https://walletpilot.com/bitcoin-tracker/etfs"
    
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', '30', url],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def parse_btc_value(text):
    """Parse BTC value from text like '1.290M BTC' or '2534 BTC' or '+2534 BTC'"""
    # Match: 1.290M BTC (millions)
    m = re.search(r'([\d.]+)\s*M\s*BTC', text, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    
    # Match: +2534 BTC or -2534 BTC or 2,534 BTC (plain integer, optional sign/commas)
    m = re.search(r'([+-]?)\s*([\d,]+)\s*BTC', text, re.IGNORECASE)
    if m:
        sign = -1 if m.group(1) == '-' else 1
        return sign * int(m.group(2).replace(',', ''))
    
    return None


def find_value_near_label(soup, label_text):
    """Find BTC value near a given label in the HTML"""
    # Search all text nodes for the label
    for text_node in soup.find_all(string=re.compile(re.escape(label_text), re.IGNORECASE)):
        # Walk up the DOM tree looking for a BTC value nearby
        element = text_node
        for _ in range(5):  # Walk up to 5 levels
            parent = element.parent if hasattr(element, 'parent') else None
            if not parent:
                break
            full_text = parent.get_text()
            val = parse_btc_value(full_text)
            if val is not None:
                return val
            element = parent
    
    return None


def parse_html_content(html):
    """Extract ETF data from walletpilot HTML content.
    
    Expected formats on walletpilot.com:
      Assets under management: 1.290M BTC
      1-Day Net Flows: +2534 BTC
      7-Day Net Flows: +10432 BTC
      30-Day Net Flows: +19407 BTC
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'totalHoldingsBTC': None,
        'flows': {
            '1day': None,
            '7day': None,
            '30day': None
        },
        'history': [],
        'lastUpdated': datetime.now().isoformat()
    }
    
    # Total BTC holdings from "Assets under management"
    data['totalHoldingsBTC'] = find_value_near_label(soup, 'Assets under management')
    print(f"  Total BTC: {data['totalHoldingsBTC']}")
    
    # Net flows
    flow_map = {
        '1day': '1-Day Net Flows',
        '7day': '7-Day Net Flows',
        '30day': '30-Day Net Flows'
    }
    
    for key, label in flow_map.items():
        data['flows'][key] = find_value_near_label(soup, label)
        print(f"  {label}: {data['flows'][key]}")
    
    # 7-day history from tables
    tables = soup.find_all('table')
    history_data = []
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                try:
                    date_text = cells[0].get_text(strip=True)
                    date_str = None
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%b %d, %Y', '%B %d, %Y', '%b %d']:
                        try:
                            date_obj = datetime.strptime(date_text, fmt)
                            date_str = date_obj.strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                    
                    if not date_str:
                        continue
                    
                    # Look for BTC values in remaining cells
                    total_btc = None
                    daily_flow = None
                    for cell in cells[1:]:
                        cell_text = cell.get_text(strip=True)
                        val = parse_btc_value(cell_text)
                        if val is not None:
                            if total_btc is None and val > 100000:
                                total_btc = val
                            elif daily_flow is None:
                                daily_flow = val
                    
                    if date_str:
                        history_data.append({
                            'date': date_str,
                            'totalBTC': total_btc,
                            'dailyFlow': daily_flow
                        })
                except:
                    continue
    
    history_data.sort(key=lambda x: x['date'], reverse=True)
    data['history'] = history_data[:7]
    
    return data

def main():
    """Main entry point"""
    print(f"Fetching ETF data at {datetime.now().isoformat()}")
    
    html = fetch_etf_data()
    
    if html:
        data = parse_html_content(html)
    else:
        data = {
            'error': 'Failed to fetch data',
            'lastUpdated': datetime.now().isoformat()
        }
    
    # Write to JSON file
    output_file = '/home/amak/findamak.github.io/etf-data.json'
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✓ Saved to {output_file}")
    
    # Commit and push to GitHub
    print("\nPushing to GitHub...")
    os.chdir('/home/amak/findamak.github.io')
    
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if result.stdout.strip():
            subprocess.run(['git', 'add', 'etf-data.json'], check=True)
            subprocess.run(['git', 'commit', '-m', f'Update ETF data at {datetime.now().strftime("%Y-%m-%d %H:%M")}'], check=True)
            subprocess.run(['git', 'push'], check=True)
            print("✓ Pushed to GitHub")
        else:
            print("  No changes to commit")
    except subprocess.CalledProcessError as e:
        print(f"✗ Git error: {e}")

if __name__ == '__main__':
    main()