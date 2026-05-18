import asyncio
import httpx
import json

async def test():
    # Try v2 endpoint
    url = "https://api.elections.kalshi.com/trade-api/v2/markets"
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
                markets = data.get("markets", [])
                print(f"Found {len(markets)} markets")
                if markets:
                    print(f"First market: {markets[0].get('id')}")
                    print(f"First market ticker: {markets[0].get('ticker')}")
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test())
