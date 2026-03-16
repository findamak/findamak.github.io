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
    import re
    
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
    
    # Extract Total BTC Holdings from "Assets under management" section
    # Look for text containing "Assets under management" and extract BTC value
    aum_section = soup.find(string=re.compile(r'Assets under management', re.IGNORECASE))
    if aum_section:
        # Navigate to parent or nearby elements to find BTC value
        parent = aum_section.find_parent() if hasattr(aum_section, 'find_parent') else None
        if parent:
            # Look for BTC pattern in the parent element
            btc_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*BTC', parent.get_text())
            if btc_match:
                data['totalHoldingsBTC'] = int(btc_match.group(1).replace(',', ''))
    
    # If not found, try finding any element with "Assets" and "BTC" nearby
    if not data['totalHoldingsBTC']:
        for element in soup.find_all(string=re.compile(r'Assets', re.IGNORECASE)):
            parent = element.find_parent() if hasattr(element, 'find_parent') else element
            text = parent.get_text() if hasattr(parent, 'get_text') else str(element)
            btc_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*BTC', text)
            if btc_match:
                data['totalHoldingsBTC'] = int(btc_match.group(1).replace(',', ''))
                break
    
    # Extract flows by looking for specific labels
    flow_labels = {
        '1day': '1-Day Net Flows',
        '7day': '7-Day Net Flows',
        '30day': '30-Day Net Flows'
    }
    
    for key, label in flow_labels.items():
        # Find element containing the label text
        label_element = soup.find(string=re.compile(re.escape(label), re.IGNORECASE))
        if label_element:
            parent = label_element.find_parent() if hasattr(label_element, 'find_parent') else label_element
            if parent:
                # Look for the value in the parent or sibling elements
                text = parent.get_text() if hasattr(parent, 'get_text') else str(label_element)
                # Match patterns like +$181M, -$45M, +$181.5M, etc.
                flow_match = re.search(r'([+-]?)\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)', text, re.IGNORECASE)
                if flow_match:
                    sign = -1 if flow_match.group(1) == '-' else 1
                    value = float(flow_match.group(2).replace(',', ''))
                    data['flows'][key] = sign * int(value * 1e6)  # Convert M to actual
    
    # Extract 7-day history from table
    # Look for table with date columns
    tables = soup.find_all('table')
    history_data = []
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                try:
                    # Extract date from first column
                    date_cell = cells[0].get_text(strip=True)
                    date_str = None
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%b %d, %Y', '%B %d, %Y']:
                        try:
                            date_obj = datetime.strptime(date_cell, fmt)
                            date_str = date_obj.strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                    
                    if not date_str:
                        continue
                    
                    # Extract BTC from second column
                    btc_cell = cells[1].get_text(strip=True)
                    btc_match = re.search(r'(\d{1,3}(?:,\d{3})*)', btc_cell)
                    total_btc = int(btc_match.group(1).replace(',', '')) if btc_match else None
                    
                    # Extract daily flow from third or fourth column
                    flow_cell = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    flow_match = re.search(r'([+-]?)\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)?', flow_cell, re.IGNORECASE)
                    daily_flow = None
                    if flow_match:
                        sign = -1 if flow_match.group(1) == '-' else 1
                        daily_flow = sign * float(flow_match.group(2).replace(',', '')) * 1e6
                    
                    if date_str and total_btc:
                        history_data.append({
                            'date': date_str,
                            'totalBTC': total_btc,
                            'dailyFlow': daily_flow
                        })
                except Exception as e:
                    continue
    
    # Keep only last 7 days, sorted by date descending
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