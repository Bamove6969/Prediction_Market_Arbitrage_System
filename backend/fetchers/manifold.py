import httpx
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

MANIFOLD_API = "https://api.manifold.markets/v0"
PAGE_SIZE = 1000
MAX_PAGES = 50  # Up to 50k markets

async def fetch_manifold_markets(limit: int = 50000, on_progress: callable = None) -> List[Dict[str, Any]]:
    markets = []
    offset = 0
    pages_fetched = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(markets) < limit and pages_fetched < MAX_PAGES:
                params = {
                    "limit": PAGE_SIZE,
                    "offset": offset,
                    "filter": "open",
                    "sort": "liquidity",
                }
                
                logger.info(f"Fetching Manifold markets offset={offset}...")
                resp = await client.get(f"{MANIFOLD_API}/search-markets", params=params)
                resp.raise_for_status()
                raw_markets = resp.json()

                if not raw_markets:
                    break

                for m in raw_markets:
                    try:
                        # We only care about BINARY and MULTIPLE_CHOICE right now for arb
                        outcome_type = m.get("outcomeType", "")
                        
                        yes_price = 0.5
                        no_price = 0.5
                        is_binary = outcome_type == "BINARY"
                        outcomes = None
                        
                        if is_binary:
                            yes_price = m.get("probability", 0.5)
                            no_price = 1.0 - yes_price
                        elif outcome_type == "MULTIPLE_CHOICE":
                            # Manifold handles multi-choice answers differently, we might skip or map them
                            # For simplicity, we skip complex multi-choice unless it's binary-like
                            answers = m.get("answers", [])
                            if answers and len(answers) == 2:
                                is_binary = True
                                yes_price = answers[0].get("probability", 0.5)
                                no_price = answers[1].get("probability", 0.5)
                            else:
                                continue # Skip non-binary multi-choice for now
                        else:
                            continue # Skip non-binary
                            
                        volume = m.get("volume", 0)
                        close_time = m.get("closeTime", None)
                        end_date = datetime.utcfromtimestamp(close_time / 1000.0).isoformat() if close_time else None

                        market = {
                            "id": f"mani_{m.get('id', '')}",
                            "platform": "Manifold",
                            "title": m.get("question", "Unknown"),
                            "category": "Unknown",
                            "yesPrice": yes_price,
                            "noPrice": no_price,
                            "volume": volume,
                            "lastUpdated": datetime.utcnow().isoformat(),
                            "endDate": end_date,
                            "marketUrl": m.get("url", ""),
                            "isBinary": is_binary,
                            "outcomeCount": 2,
                            "contractLabel": "Yes",
                            "outcomes": outcomes,
                        }
                        markets.append(market)
                    except Exception as e:
                        logger.warning(f"Skipping Manifold market: {e}")
                        continue

                pages_fetched += 1
                offset += PAGE_SIZE
                
                if on_progress:
                    on_progress(f"fetched {len(markets)} Manifold markets")

                if len(raw_markets) < PAGE_SIZE:
                    break  # No more results
                    
                # Rate limit protection: Manifold allows 500 req/min, but let's be nice
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Error fetching Manifold markets: {e}")

    logger.info(f"Successfully fetched {len(markets)} Manifold markets.")
    return markets[:limit]
