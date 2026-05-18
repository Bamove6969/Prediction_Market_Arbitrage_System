
import asyncio
import logging
import httpx
from datetime import datetime

# Direct test of the API endpoint to see the structure
async def debug_kalshi():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://kalshi.com/",
        "Origin": "https://kalshi.com"
    }
    
    # Try a few common search endpoints
    endpoints = [
        "https://api.elections.kalshi.com/v1/search/series?order_by=trending&page_size=10&status=open",
        "https://api.elections.kalshi.com/v1/search/event?order_by=trending&page_size=10&status=open",
        "https://api.kalshi.com/trade-api/v2/markets?limit=10" # Standard API 
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in endpoints:
            print(f"\nTrying: {url}")
            try:
                resp = await client.get(url, headers=headers)
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    # Print keys to understand structure
                    print(f"Keys: {list(data.keys())}")
                    if 'series' in data and data['series']:
                        print(f"First series ticker: {data['series'][0].get('series_ticker')}")
                    elif 'markets' in data and data['markets']:
                        print(f"First market title: {data['markets'][0].get('title')}")
                else:
                    print(f"Error Body: {resp.text[:200]}")
            except Exception as e:
                print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_kalshi())
