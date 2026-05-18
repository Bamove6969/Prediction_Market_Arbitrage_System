import httpx
import asyncio
import logging
import os
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# NOTE: Using elections/demo API by default - markets may not exist on production Kalshi.
# Override with env var KALSHI_API_BASE when you have access.
KALSHI_API = os.getenv("KALSHI_API_BASE", "https://api.elections.kalshi.com/trade-api/v2").rstrip("/")
PAGE_SIZE = 1000
MAX_PAGES = 500


def _parse_market(m: dict) -> dict | None:
    if m.get("market_type") != "binary":
        return None

    # Outcome labels (preserve non-Yes/No labels like Up/Down, Biden/Trump)
    yes_label = (m.get("yes_sub_title") or "Yes").strip()
    no_label = (m.get("no_sub_title") or "No").strip()

    # Skip bundled/multivariate markets where labels are essentially a long list.
    # These aren't the 2-choice questions you want.
    if len(yes_label) > 60 or len(no_label) > 60 or "," in yes_label or "," in no_label:
        return None

    yes_price = 0.0

    # Preferred: explicit yes_price in cents (docs commonly show this)
    if m.get("yes_price") is not None:
        try:
            yes_price = float(m.get("yes_price")) / 100.0
        except (ValueError, TypeError):
            yes_price = 0.0
    else:
        # Fallback: bid/ask/last in dollars (string fields)
        yes_bid = m.get("yes_bid_dollars", "0")
        yes_ask = m.get("yes_ask_dollars", "0")
        try:
            yes_bid_f = float(yes_bid) if yes_bid else 0
            yes_ask_f = float(yes_ask) if yes_ask else 0
        except (ValueError, TypeError):
            yes_bid_f = 0
            yes_ask_f = 0

        if yes_bid_f > 0 and yes_ask_f > 0:
            yes_price = (yes_bid_f + yes_ask_f) / 2
        elif yes_ask_f > 0:
            yes_price = yes_ask_f
        elif yes_bid_f > 0:
            yes_price = yes_bid_f
        else:
            last_price = m.get("last_price_dollars", "0")
            try:
                yes_price = float(last_price) if last_price else 0
            except (ValueError, TypeError):
                yes_price = 0

    if yes_price <= 0 or yes_price >= 1:
        return None

    no_price = 1.0 - yes_price

    volume_str = m.get("volume", 0)
    try:
        volume = int(volume_str) if volume_str else 0
    except (ValueError, TypeError):
        volume = 0

    ticker = m.get("ticker", "")
    event_ticker = m.get("event_ticker", "")
    title_text = m.get("title", "")
    
    # Kalshi website URLs are not guaranteed to be derivable from ticker.
    # Prefer a canonical URL from the API when present; otherwise fall back to search.
    market_url = None
    if m.get("url"):
        market_url = m.get("url")
        if market_url and not market_url.startswith("http"):
            market_url = f"https://kalshi.com{market_url}"
    elif title_text:
        from urllib.parse import quote
        market_url = f"https://kalshi.com/browse?q={quote(title_text)}"

    return {
        "id": f"kalshi_{ticker}",
        "platform": "Kalshi",
        "title": m.get("title", "Unknown"),
        "category": m.get("subtitle", event_ticker),
        "yesPrice": round(yes_price, 4),
        "noPrice": round(no_price, 4),
        "volume": volume,
        "lastUpdated": datetime.utcnow().isoformat(),
        "endDate": m.get("close_time") or m.get("expiration_time"),
        "marketUrl": market_url,
        "isBinary": True,
        "outcomeCount": 2,
        "contractLabel": yes_label,
        "outcomes": [
            {"name": yes_label, "price": round(yes_price, 4)},
            {"name": no_label, "price": round(no_price, 4)},
        ],
    }


async def fetch_kalshi_markets(limit: int = 10000, on_progress: callable = None) -> List[Dict[str, Any]]:
    markets = []
    cursor = None
    pages_fetched = 0
    consecutive_empty = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(markets) < limit and pages_fetched < MAX_PAGES:
                params = {
                    "status": "open",
                    "limit": PAGE_SIZE,
                }
                if cursor:
                    params["cursor"] = cursor

                for attempt in range(3):
                    resp = await client.get(f"{KALSHI_API}/markets", params=params)
                    if resp.status_code == 429:
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"Kalshi rate limited, waiting {wait}s (attempt {attempt+1}/3)")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    break
                else:
                    logger.error("Kalshi rate limit exceeded after 3 retries, stopping pagination")
                    break
                data = resp.json()

                raw_markets = data.get("markets", [])
                if not raw_markets:
                    break

                page_binary = 0
                for m in raw_markets:
                    try:
                        parsed = _parse_market(m)
                        if parsed:
                            markets.append(parsed)
                            page_binary += 1
                    except Exception as e:
                        logger.warning(f"Skipping Kalshi market: {e}")
                        continue

                pages_fetched += 1
                cursor = data.get("cursor")

                # Report progress
                if on_progress:
                    on_progress(pages_fetched, len(markets))

                if pages_fetched % 50 == 0:
                    logger.info(f"Kalshi page {pages_fetched}: {len(raw_markets)} raw, +{page_binary} binary (total: {len(markets)})")

                if not cursor or len(raw_markets) < PAGE_SIZE:
                    break

                if page_binary == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0
                if consecutive_empty >= 20:
                    logger.info(f"Kalshi: stopping early after {consecutive_empty} consecutive pages with 0 binary markets")
                    break

                if pages_fetched % 20 == 0:
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(0.05)

    except Exception as e:
        logger.error(f"Kalshi fetch error: {e}")

    logger.info(f"Kalshi total: {len(markets)} binary markets from {pages_fetched} pages")
    return markets
