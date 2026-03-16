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

def parse_html_content(html):
    """Extract ETF data from walletpilot HTML content"""
    from bs4 import BeautifulSoup
    import re
    
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        'totalHoldingsBTC': None,
        'totalAUM': None,
        'flows': {
            '1day': None,
            '7day': None,
            '30day': None
        },
        'history': [],
        'lastUpdated': datetime.now().isoformat()
    }
    
    # Extract total BTC holdings - look for patterns like "1,290,200 BTC" or similar
    btc_patterns = [
        r'(\d{1,3}(?:,\d{3})*)\s*BTC',
        r'Total.*?(\d{1,3}(?:,\d{3})*)',
    ]
    
    for pattern in btc_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            btc_str = match.group(1).replace(',', '')
            try:
                data['totalHoldingsBTC'] = int(btc_str)
                break
            except:
                pass
    
    # Extract AUM - look for patterns like "$91.8B" or "$91.8 billion"
    aum_patterns = [
        r'\$(\d+(?:\.\d+)?)\s*(?:B|billion)',
        r'AUM.*?\$(\d+(?:\.\d+)?)\s*(?:B|billion)',
    ]
    
    for pattern in aum_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            try:
                data['totalAUM'] = float(match.group(1)) * 1e9
                break
            except:
                pass
    
    # Extract flows - look for patterns like "+$181M" or "-$45M"
    flow_patterns = {
        '1day': [r'(?:1[- ]?[Dd]ay|24[- ]?[Hh]).*?([+-]?\$?\d+(?:\.\d+)?)\s*(?:M|million)'],
        '7day': [r'(?:7[- ]?[Dd]ay|1[- ]?[Ww]eek).*?([+-]?\$?\d+(?:\.\d+)?)\s*(?:M|million)'],
        '30day': [r'(?:30[- ]?[Dd]ay|1[- ]?[Mm]onth).*?([+-]?\$?\d+(?:\.\d+)?)\s*(?:M|million)']
    }
    
    for period, patterns in flow_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                flow_str = match.group(1).replace('$', '').replace(',', '')
                try:
                    value = float(flow_str)
                    # Handle +/- prefix
                    if '+' in match.group(1) or (not '-' in match.group(1) and value > 0):
                        value = abs(value)
                    elif '-' in match.group(1):
                        value = -abs(value)
                    data['flows'][period] = int(value * 1e6)  # Convert M to actual
                    break
                except:
                    pass
    
    # Extract 7-day history from table
    # Look for table rows with date, btc, aum, flow data
    history_rows = soup.find_all('tr')
    history_data = []
    
    for row in history_rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 4:
            try:
                # Extract date
                date_cell = cells[0].get_text(strip=True)
                # Try to parse date
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%b %d, %Y']:
                    try:
                        date_obj = datetime.strptime(date_cell, fmt)
                        date_str = date_obj.strftime('%Y-%m-%d')
                        break
                    except:
                        date_str = date_cell
                
                # Extract BTC
                btc_cell = cells[1].get_text(strip=True)
                btc_match = re.search(r'(\d+(?:,\d+)*)', btc_cell)
                total_btc = int(btc_match.group(1).replace(',', '')) if btc_match else None
                
                # Extract AUM
                aum_cell = cells[2].get_text(strip=True)
                aum_match = re.search(r'\$(\d+(?:\.\d+)?)\s*(?:B|billion)?', aum_cell, re.IGNORECASE)
                total_aum = float(aum_match.group(1)) * 1e9 if aum_match else None
                
                # Extract daily flow
                flow_cell = cells[3].get_text(strip=True)
                flow_match = re.search(r'([+-]?)\$?(\d+(?:\.\d+)?)\s*(?:M|million)?', flow_cell, re.IGNORECASE)
                if flow_match:
                    sign = -1 if flow_match.group(1) == '-' else 1
                    daily_flow = sign * float(flow_match.group(2)) * 1e6
                else:
                    daily_flow = None
                
                if date_str and total_btc:
                    history_data.append({
                        'date': date_str,
                        'totalBTC': total_btc,
                        'totalAUM': total_aum,
                        'dailyFlow': daily_flow
                    })
            except Exception as e:
                continue
    
    # Keep only last 7 days
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