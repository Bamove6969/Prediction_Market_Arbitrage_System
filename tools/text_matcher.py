#!/usr/bin/env python3
"""
Text-based market matcher (no GPU required)
Uses keyword and entity extraction to find semantically similar questions
"""

import asyncio
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict

from backend.fetchers.polymarket import fetch_polymarket_markets
from backend.fetchers.predictit import fetch_predictit_markets


ENTITY_KEYWORDS = {
    'trump': ['trump', 'donald'],
    'biden': ['biden', 'joe'],
    'republican': ['republican', 'gop', 'conservative'],
    'democrat': ['democrat', 'liberal', 'democratic'],
    'governor': ['governor', 'governor race'],
    'senate': ['senate', 'senator'],
    'house': ['house', 'representative', 'congress'],
    'fed': ['fed', 'federal reserve', 'interest rate'],
    'nato': ['nato'],
    'greenland': ['greenland'],
    'china': ['china', 'chinese', 'xi'],
    'russia': ['russia', 'russian', 'putin'],
    'ukraine': ['ukraine', 'ukrainian', 'zelensky'],
    'israel': ['israel', 'israeli', 'netanyahu'],
    'election': ['election', 'vote'],
    'impeachment': ['impeach'],
    'tariff': ['tariff', 'trade war'],
    'economy': ['gdp', 'recession', 'inflation', 'cpi'],
    'crypto': ['bitcoin', 'btc', 'ethereum', 'crypto'],
}


def extract_keywords(title: str) -> set:
    title = title.lower()
    keywords = set()
    
    # Extract 4+ letter words
    words = re.findall(r'\b[a-z]{4,}\b', title)
    keywords.update(words)
    
    # Add entity keywords
    for entity, aliases in ENTITY_KEYWORDS.items():
        for alias in aliases:
            if alias in title:
                keywords.add(entity)
                break
    
    return keywords


def get_shared_entities(title_a: str, title_b: str) -> set:
    kw_a = extract_keywords(title_a)
    kw_b = extract_keywords(title_b)
    return kw_a & kw_b


def get_compatibility_score(title_a: str, title_b: str) -> float:
    """Calculate simple compatibility score"""
    shared = get_shared_entities(title_a, title_b)
    
    if not shared:
        return 0.0
    
    # Check for critical mismatches
    title_a = title_a.lower()
    title_b = title_b.lower()
    
    # Different years check
    year_a = re.search(r'202[56789]', title_a)
    year_b = re.search(r'202[56789]', title_b)
    
    if year_a and year_b:
        if year_a.group() != year_b.group():
            return 0.0  # Different years - not the same question
    
    # Same political party check (don't match R to D)
    dem_a = 'democrat' in title_a
    dem_b = 'democrat' in title_b
    rep_a = 'republican' in title_a or 'gop' in title_a
    rep_b = 'republican' in title_b or 'gop' in title_b
    
    if (dem_a and rep_b) or (rep_a and dem_b):
        return 0.0  # Different parties - not matching
    
    return min(1.0, len(shared) * 0.25)


def find_candidates(poly_markets: List, pi_markets: List) -> List[Dict]:
    """Find candidate matching pairs"""
    # Build keyword index
    pi_by_keyword = defaultdict(list)
    for pim in pi_markets:
        kws = extract_keywords(pim['title'])
        for kw in kws:
            pi_by_keyword[kw].append(pim)
    
    candidates = []
    seen = set()
    
    for pm in poly_markets:
        kws = extract_keywords(pm['title'])
        
        for kw in kws:
            if kw in pi_by_keyword:
                for pim in pi_by_keyword[kw]:
                    score = get_compatibility_score(pm['title'], pim['title'])
                    
                    if score > 0.3:
                        pair_key = tuple(sorted([pm['id'], pim['id']]))
                        if pair_key not in seen:
                            seen.add(pair_key)
                            candidates.append({
                                'poly': pm,
                                'pi': pim,
                                'score': score,
                                'shared': get_shared_entities(pm['title'], pim['title']),
                            })
    
    return candidates


def calculate_arbitrage(pair: Dict) -> List[Dict]:
    """Find arbitrage between a pair"""
    pm_yes = pair['poly']['yesPrice']
    pi_yes = pair['pi']['yesPrice']
    
    spread = abs(pm_yes - pi_yes)
    
    if spread > 0.08:  # 8% min spread
        higher = 'poly' if pm_yes > pi_yes else 'pi'
        lower = 'pi' if pm_yes > pi_yes else 'poly'
        
        return [{
            'type': f'Long {higher}, Short {lower}',
            'spread': spread * 100,
            'poly_yes': pm_yes,
            'pi_yes': pi_yes,
        }]
    
    return []


async def main():
    print("=" * 60)
    print("KEYWORD-BASED MARKET MATCHER")
    print("=" * 60)
    
    # Fetch markets
    print("\n1. Fetching Polymarket...")
    poly = await fetch_polymarket_markets(limit=500)
    print(f"   {len(poly)} markets")
    
    print("\n2. Fetching PredictIt...")
    pi = await fetch_predictit_markets()
    print(f"   {len(pi)} markets")
    
    # Filter active
    poly_active = [m for m in poly if 0.15 < m['yesPrice'] < 0.85]
    pi_active = [m for m in pi if 0.15 < m['yesPrice'] < 0.85]
    
    print(f"\n3. Active: Poly={len(poly_active)}, PI={len(pi_active)}")
    
    # Find candidates
    print("\n4. Finding matches...")
    candidates = find_candidates(poly_active, pi_active)
    print(f"   {len(candidates)} pairs")
    
    # Calculate arbitrage
    arbs = []
    for c in candidates:
        arb = calculate_arbitrage(c)
        if arb:
            arbs.append({**c, 'arbs': arb})
    
    # Sort by score + spread
    arbs.sort(key=lambda x: (x['score'], x['arbs'][0]['spread']), reverse=True)
    
    print(f"\n5. Found {len(arbs)} arbitrage opportunities")
    
    # Print top results
    print("\n" + "=" * 60)
    print("TOP ARBITRAGE OPPORTUNITIES")
    print("=" * 60)
    
    shown = 0
    for a in arbs:
        if shown >= 15:
            break
        
        pm, pim = a['poly'], a['pi']
        
        print(f"\n{a['score']:.0%} match | {a['arbs'][0]['spread']:.0f}% spread")
        print(f"  Poly: {pm['title'][:60]}")
        print(f"    Yes: {pm['yesPrice']:.2f}")
        print(f"  PI:   {pim['title'][:60]}")
        print(f"    Yes: {pim['yesPrice']:.2f}")
        
        for arb in a['arbs']:
            if arb['spread'] > 10:
                higher = 'Poly' if arb['poly_yes'] > arb['pi_yes'] else 'PI'
                lower = 'PI' if arb['poly_yes'] > arb['pi_yes'] else 'Poly'
                print(f"  Trade: Long {higher}, Short {lower}")
        
        shown += 1
    
    return arbs


if __name__ == "__main__":
    asyncio.run(main())