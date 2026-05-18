
import asyncio
import logging
from backend.fetchers.kalshi_scraper import scrape_kalshi_markets

async def test_scraper():
    logging.basicConfig(level=logging.INFO)
    print("Testing Kalshi Scraper...")
    markets = await scrape_kalshi_markets(limit=10)
    print(f"Found {len(markets)} markets.")
    for m in markets[:3]:
        print(f"Title: {m['title']}")
        print(f"Price: {m['yesPrice']}")
        print(f"URL: {m['marketUrl']}")
        print("-" * 20)

if __name__ == "__main__":
    asyncio.run(test_scraper())
