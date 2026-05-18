import asyncio
import httpx
import json

async def test():
    url = "https://api.elections.kalshi.com/v1/search/series?order_by=trending&page_size=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://kalshi.com/",
        "Origin": "https://kalshi.com"
    }
    async with httpx.AsyncClient(http2=True) as client:
        try:
            resp = await client.get(url, headers=headers)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                series = data.get("series", [])
                print(f"Found {len(series)} series")
                if series:
                    print(f"First series: {series[0].get('series_ticker')}")
                    markets = series[0].get("markets", [])
                    print(f"Markets in first series: {len(markets)}")
            else:
                print(f"Error: {resp.text[:200]}")
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test())
