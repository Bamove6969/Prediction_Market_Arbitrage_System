#!/usr/bin/env python3
"""
Semantic Market Matcher
Uses sentence-transformers for fast semantic matching between markets
"""

import asyncio
import json
import re
from typing import List, Dict, Any, Tuple, Set
from collections import defaultdict

try:
    from sentence_transformers import SentenceTransformer, util
    import torch
    HAS_ST = True
except ImportError:
    HAS_ST = False
    print("Warning: sentence-transformers not installed. Run: pip install sentence-transformers torch")

from backend.fetchers.polymarket import fetch_polymarket_markets
from backend.fetchers.predictit import fetch_predictit_markets


def extract_date_key(title: str) -> Set[str]:
    """Extract date-related keywords"""
    dates = set()
    months = ['january', 'february', 'march', 'april', 'may', 'june', 
              'july', 'august', 'september', 'october', 'november', 'december']
    title_lower = title.lower()
    for m in months:
        if m in title_lower:
            dates.add(m)
    if '2026' in title: dates.add('2026')
    if '2027' in title: dates.add('2027')
    return dates


def extract_entity_key(title: str) -> Set[str]:
    """Extract key entities (people, organizations, locations)"""
    title_lower = title.lower()
    entities = set()
    
    # Political keywords
    if 'trump' in title_lower: entities.add('trump')
    if 'biden' in title_lower: entities.add('biden')
    if 'republican' in title_lower or 'gop' in title_lower: entities.add('republican')
    if 'democrat' in title_lower: entities.add('democrat')
    if 'governor' in title_lower: entities.add('governor')
    if 'senate' in title_lower: entities.add('senate')
    if 'house' in title_lower: entities.add('house')
    if 'fed' in title_lower or 'federal reserve' in title_lower: entities.add('fed')
    if 'nato' in title_lower: entities.add('nato')
    if 'greenland' in title_lower: entities.add('greenland')
    
    return entities


def get_compatibility_factors(title_a: str, title_b: str) -> Dict[str, Any]:
    """Check if two questions could be the same"""
    # Date compatibility
    dates_a = extract_date_key(title_a)
    dates_b = extract_date_key(title_b)
    same_dates = dates_a & dates_b if dates_a and dates_b else set()
    
    # Entity compatibility
    ents_a = extract_entity_key(title_a)
    ents_b = extract_entity_key(title_b)
    shared_ents = ents_a & ents_b
    
    return {
        'shared_dates': same_dates,
        'shared_entities': shared_ents,
        'dates_a': dates_a,
        'ents_a': ents_a,
        'dates_b': dates_b,
        'ents_b': ents_b,
    }


def semantic_filter_candidates(poly_markets: List, pi_markets: List, 
                              threshold: float = 0.65) -> List[Tuple]:
    """
    Fast filter using simple text matching (placeholder for GPU matching)
    Returns candidate pairs for detailed comparison
    """
    if not HAS_ST:
        print("Using fallback text matching")
        return _text_based_filter(poly_markets, pi_markets)
    
    print(f"Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print(f"Encoding {len(poly_markets) + len(pi_markets)} markets...")
    
    all_titles = [m['title'] for m in poly_markets] + [m['title'] for m in pi_markets]
    embeddings = model.encode(all_titles, show_progress_bar=True, batch_size=64)
    
    poly_emb = embeddings[:len(poly_markets)]
    pi_emb = embeddings[len(poly_markets):]
    
    print("Computing similarities...")
    # Compute cosine similarities in batches
    candidates = []
    batch_size = 100
    
    for i in range(0, len(poly_emb), batch_size):
        batch_emb = poly_emb[i:i+batch_size]
        # Compute against all PI markets
        similarities = util.cos_sim(batch_emb, pi_emb)
        
        for j, sim_row in enumerate(similarities):
            poly_idx = i + j
            poly_m = poly_markets[poly_idx]
            
            # Find top matches
            top_matches = torch.topk(sim_row, k=3)
            
            for pi_idx, score in zip(top_matches.indices, top_matches.values):
                score = score.item()
                if score >= threshold:
                    pi_m = pi_markets[pi_idx]
                    
                    # Check basic compatibility
                    compat = get_compatibility_factors(poly_m['title'], pi_m['title'])
                    
                    if compat['shared_entities']:
                        candidates.append({
                            'poly': poly_m,
                            'pi': pi_m,
                            'score': score,
                            'shared_entities': compat['shared_entities'],
                            'shared_dates': compat['shared_dates'],
                        })
    
    return candidates


def _text_based_filter(poly_markets: List, pi_markets: List) -> List[Tuple]:
    """Fallback text-based matching"""
    candidates = []
    
    # Build keyword index for PI
    pi_keywords = defaultdict(list)
    for pim in pi_markets:
        words = set(re.findall(r'\b\w{4,}\b', pim['title'].lower()))
        for w in words:
            pi_keywords[w].append(pim)
    
    # Find matches
    for pm in poly_markets:
        words = re.findall(r'\b\w{4,}\b', pm['title'].lower())
        
        for w in words:
            if w in pi_keywords:
                for pim in pi_keywords[w]:
                    compat = get_compatibility_factors(pm['title'], pim['title'])
                    if compat['shared_entities']:
                        candidates.append({
                            'poly': pm,
                            'pi': pim,
                            'score': 0.7,  # Conservative estimate
                            'shared_entities': compat['shared_entities'],
                        })
    
    return candidates


def find_arbitrage(pair: Dict) -> List[Dict]:
    """Calculate arbitrage profitability"""
    pm_yes = pair['poly']['yesPrice']
    pi_yes = pair['pi']['yesPrice']
    
    spread = abs(pm_yes - pi_yes)
    
    if spread > 0.10:  # 10% minimum spread
        higher = 'poly' if pm_yes > pi_yes else 'pi'
        lower = 'pi' if pm_yes > pi_yes else 'poly'
        
        return [{
            'type': f'Long {higher}, Short {lower}',
            'spread': spread * 100,
            'profit': f'{spread * 100:.1f}%',
            'poly_yes': pm_yes,
            'pi_yes': pi_yes,
        }]
    
    return []


async def run_matcher():
    """Main matching pipeline"""
    print("=" * 60)
    print("SEMANTIC MARKET MATCHER")
    print("=" * 60)
    
    # Fetch markets
    print("\n1. Fetching Polymarket...")
    poly_markets = await fetch_polymarket_markets(limit=500)
    print(f"   Got {len(poly_markets)} markets")
    
    print("\n2. Fetching PredictIt...")
    pi_markets = await fetch_predictit_markets()
    print(f"   Got {len(pi_markets)} markets")
    
    # Filter to active range (avoid trivial markets)
    poly_active = [m for m in poly_markets if 0.15 < m['yesPrice'] < 0.85]
    pi_active = [m for m in pi_markets if 0.15 < m['yesPrice'] < 0.85]
    
    print(f"\n3. Active markets: Poly={len(poly_active)}, PI={len(pi_active)}")
    
    # Find candidates
    print("\n4. Finding semantic matches...")
    candidates = semantic_filter_candidates(poly_active, pi_active, threshold=0.65)
    print(f"   Found {len(candidates)} candidate pairs")
    
    # Calculate arbitrage
    print("\n5. Calculating arbitrage...")
    arbs = []
    for c in candidates:
        arb = find_arbitrage(c)
        if arb:
            arbs.append({**c, 'arbs': arb})
    
    # Sort by score
    arbs.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n6. Found {len(arbs)} arbitrage opportunities")
    
    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    for a in arbs[:15]:
        print(f"\nScore: {a['score']:.0%}")
        print(f"  Poly: {a['poly']['title'][:65]}")
        print(f"    Yes: {a['poly']['yesPrice']:.2f}")
        print(f"  PI:  {a['pi']['title'][:65]}")
        print(f"    Yes: {a['pi']['yesPrice']:.2f}")
        print(f"  Match: {a['shared_entities']}")
        
        for arb in a['arbs']:
            if arb['spread'] > 15:
                print(f"  ** ARBITRAGE: {arb['spread']:.1f}% **")
    
    return arbs


if __name__ == "__main__":
    asyncio.run(run_matcher())