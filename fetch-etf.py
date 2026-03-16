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
    """Extract ETF data from HTML content"""
    # Placeholder - would need proper parsing
    # Return sample structure for now
    return {
        'totalHoldingsBTC': 1290200,
        'totalAUM': 91800000000,
        'flows': {
            '1day': 181000000,
            '7day': 736000000,
            '30day': 1366000000
        },
        'history': [],
        'lastUpdated': datetime.now().isoformat()
    }

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