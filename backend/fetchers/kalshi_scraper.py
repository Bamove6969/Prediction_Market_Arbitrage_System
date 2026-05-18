"""
Kalshi Web Scraper - Fixed to bypass API 404 block.
Uses a simplified, reliable approach that mimics a basic browser request.
"""
import httpx
import asyncio
import logging
import json
from typing import List, Dict, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

async def scrape_kalshi_markets(limit: int = 2000, on_progress: Callable = None) -> List[Dict[str, Any]]:
    """
    Fetches real-time market data directly from the public web interface sources.
    This replaces the institutional API with the same live feed used on kalshi.com.
    """
    markets = []
    
    # Minimalist headers that often bypass WAF / anti-scraping checks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://kalshi.com/",
        "Origin": "https://kalshi.com"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 1. Try V1 search (Event-based, richer data)
            url_v1 = "https://api.elections.kalshi.com/v1/search/series?order_by=trending&page_size=100"
            logger.info("Attempting Kalshi V1 fetch...")
            resp = await client.get(url_v1, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                series = data.get("series", [])
                for s in series:
                    series_title = s.get("series_title", "Unknown")
                    series_cat = s.get("category", "")
                    for m in s.get("markets", []):
                        try:
                            # Convert cents to dollars for V1
                            bid = m.get("yes_bid", 0)
                            ask = m.get("yes_ask", 0)
                            
                            price = (bid + ask) / 2 / 100 if ask > 0 else m.get("last_price", 0) / 100
                            if price <= 0 or price >= 1:
                                continue

                            markets.append({
                                "id": f"kalshi_{m.get('ticker', '')}",
                                "platform": "Kalshi",
                                "title": m.get("title", series_title),
                                "category": series_cat,
                                "yesPrice": round(price, 4),
                                "noPrice": round(1 - price, 4),
                                "volume": int(m.get("volume", 0)),
                                "lastUpdated": datetime.utcnow().isoformat(),
                                "endDate": m.get("expiration_time"),
                                "marketUrl": f"https://kalshi.com/browse/event/{s.get('event_ticker', m.get('ticker', ''))}",
                                "isBinary": True,
                                "outcomeCount": 2,
                                "contractLabel": "Yes"
                            })
                        except Exception:
                            continue
                    if len(markets) >= limit:
                        break

            # 2. If V1 found very few, supplement or fallback with V2 (Raw markets)
            if len(markets) < 10:
                logger.info(f"Kalshi V1 returned only {len(markets)} results, trying V2 for more...")
                url_v2 = "https://api.elections.kalshi.com/trade-api/v2/markets"
                resp = await client.get(url_v2, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    markets_v2 = data.get("markets", [])
                    # Track IDs we already have to avoid duplicates
                    existing_ids = {m["id"] for m in markets}
                    
                    for m in markets_v2:
                        try:
                            ticker = m.get("ticker", "")
                            if not ticker or f"kalshi_{ticker}" in existing_ids:
                                continue
                            
                            # V2 prices are already in units of 1
                            yes_price = m.get("yes_price") or (m.get("last_price", 0))
                            if yes_price <= 0 or yes_price >= 1:
                                continue

                            markets.append({
                                "id": f"kalshi_{ticker}",
                                "platform": "Kalshi",
                                "title": m.get("title", "Kalshi Market"),
                                "category": m.get("category", "General"),
                                "yesPrice": round(yes_price, 4),
                                "noPrice": round(1 - yes_price, 4),
                                "volume": int(m.get("volume", 0)),
                                "lastUpdated": datetime.utcnow().isoformat(),
                                "endDate": m.get("expiration_time"),
                                "marketUrl": f"https://kalshi.com/markets/{ticker}",
                                "isBinary": True,
                                "outcomeCount": 2,
                                "contractLabel": "Yes"
                            })
                        except Exception:
                            continue
                        if len(markets) >= limit:
                            break

            # Save a snapshot for debugging
            if markets:
                with open("kalshi_markets.json", "w", encoding="utf-8") as f:
                    json.dump(markets, f, indent=2)
                
    except Exception as e:
        logger.error(f"Kalshi scraper failed: {e}")
    
    logger.info(f"Kalshi scraper: Found {len(markets)} markets.")
    return markets
