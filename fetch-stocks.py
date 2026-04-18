#!/usr/bin/env python3
"""
Fetch stock/commodity prices using yfinance
Run periodically via cron to update stock-prices.json
"""

import yfinance as yf
import json
from datetime import datetime

# Define tickers and their display info
TICKERS = {
    'IREN': {'name': 'Iris Energy', 'type': 'stock'},
    'CIFR': {'name': 'Cipher Mining', 'type': 'stock'},
    'IBTC.XA': {'name': 'Monochrome Bitcoin ETF', 'type': 'stock'},
    'VBTC.AX': {'name': 'Vaneck Bitcoin ETF', 'type': 'stock'},
    'TAO22974-USD': {'name': 'Bittensor USD', 'type': 'stock'},
    'CC37263-USD': {'name': 'Canton Network USD', 'type': 'stock'},
    'QQQI': {'name': 'Neos Nasdaq 100 Income ETF', 'type': 'stock'},
    'GPIX': {'name': 'Goldman Sachs Income ETF', 'type': 'stock'},
    'VEA': {'name': 'Vanguard FTSE Developed markets ETF', 'type': 'stock'},
    'VEU': {'name': 'Vanguard FTSE All-world ex-US ETF', 'type': 'stock'},
    'VWO': {'name': 'Vanguard Emerging markets ETF', 'type': 'stock'},
    'STRC': {'name': 'Strategy STRC', 'type': 'stock'},
    'XLE': {'name': 'Energy ETF', 'type': 'stock'},
    'SMH': {'name': 'Semi ETF', 'type': 'stock'},
    'GLW': {'name': 'Corning Inc', 'type': 'stock'},
    '^GSPC': {'symbol': 'SPX', 'name': 'S&P 500', 'type': 'index'},
    '^NDX': {'symbol': 'NDX', 'name': 'NASDAQ 100', 'type': 'index'},
    'GC=F': {'symbol': 'GOLD', 'name': 'Gold/oz', 'type': 'commodity'},
    'SI=F': {'symbol': 'SILVER', 'name': 'Silver/oz', 'type': 'commodity'},
    'BZ=F': {'symbol': 'BZ', 'name': 'Brent Crude', 'type': 'commodity'},
    'CL=F': {'symbol': 'CL', 'name': 'WTI Crude', 'type': 'commodity'},
    'AUDUSD=X': {'symbol': 'USDAUD', 'name': 'USD/AUD', 'type': 'forex'}
}

def fetch_prices():
    """Fetch all ticker prices and return as list"""
    results = []
    
    for ticker_symbol, info in TICKERS.items():
        try:
            ticker = yf.Ticker(ticker_symbol)
            data = ticker.fast_info
            
            # Get current price
            price = data.get('lastPrice', data.get('previousClose', 0))
            
            # Get change percentage
            hist = ticker.history(period='2d')
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((price - prev_close) / prev_close) * 100
            else:
                change_pct = data.get('regularMarketChangePercent', 0)
            
            # Handle display symbol
            display_symbol = info.get('symbol', ticker_symbol)
            
            # For USDAUD, invert the rate (AUDUSD=X gives AUD per USD, we want USD per AUD)
            if ticker_symbol == 'AUDUSD=X':
                price = 1 / price if price else 0
                change_pct = -change_pct  # Invert change too
            
            results.append({
                'symbol': display_symbol,
                'name': info['name'],
                'price': round(price, 4) if price else None,
                'change': round(change_pct, 2) if change_pct else 0,
                'type': info['type']
            })
            
            print(f"✓ {display_symbol}: ${price:.4f} ({change_pct:+.2f}%)")
            
        except Exception as e:
            print(f"✗ {ticker_symbol}: {e}")
            results.append({
                'symbol': info.get('symbol', ticker_symbol),
                'name': info['name'],
                'price': None,
                'change': None,
                'type': info['type'],
                'error': str(e)
            })
    
    return results

def main():
    """Main entry point"""
    import subprocess
    import os
    
    print(f"Fetching stock prices at {datetime.now().isoformat()}")
    
    prices = fetch_prices()
    
    output = {
        'prices': prices,
        'lastUpdated': datetime.now().isoformat()
    }
    
    # Write to JSON file
    output_file = '/home/amak/findamak.github.io/stock-prices.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Saved to {output_file}")
    print(f"  Total tickers: {len(prices)}")
    
    # Commit and push to GitHub
    print("\nPushing to GitHub...")
    os.chdir('/home/amak/findamak.github.io')
    
    try:
        # Check if there are changes
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if result.stdout.strip():
            # There are changes to commit
            subprocess.run(['git', 'add', 'stock-prices.json'], check=True)
            subprocess.run(['git', 'commit', '-m', f'Update stock prices at {datetime.now().strftime("%Y-%m-%d %H:%M")}'], check=True)
            subprocess.run(['git', 'push'], check=True)
            print("✓ Pushed to GitHub")
        else:
            print("  No changes to commit")
    except subprocess.CalledProcessError as e:
        print(f"✗ Git error: {e}")

if __name__ == '__main__':
    main()
