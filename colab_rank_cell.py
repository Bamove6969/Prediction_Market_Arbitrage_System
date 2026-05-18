# 5. Rank & Filter to Top 500 Best Opportunities (Colab does the heavy lifting!)
import datetime

TOP_N = 500

def compute_composite_score(pair):
    roi = pair.get('roi', 0)
    match_score = pair.get('matchScore', 0)

    # Normalize ROI: cap at 50% (anything above is a bonus)
    roi_norm = min(roi, 50.0) / 50.0

    # Normalize match quality: 75–100 range → 0.0 to 1.0
    match_norm = max(0.0, (match_score - 75.0)) / 25.0

    # Time urgency: markets ending sooner score higher
    # 1.0 = ending today, 0.0 = ending in 30+ days
    urgency_norm = 0.0
    end_dates = []
    for ed in [pair['marketA'].get('endDate'), pair['marketB'].get('endDate')]:
        if ed:
            try:
                dt = datetime.datetime.fromisoformat(str(ed).replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                end_dates.append(dt)
            except Exception:
                pass
    if end_dates:
        soonest = min(end_dates)
        now = datetime.datetime.now(datetime.timezone.utc)
        days_left = (soonest - now).total_seconds() / 86400
        if 0 < days_left <= 30:
            urgency_norm = (30.0 - days_left) / 30.0
        # Already expired or > 30 days away = 0 urgency bonus

    # Composite: ROI 60% + Match Quality 20% + Time Urgency 20%
    return (roi_norm * 0.6) + (match_norm * 0.2) + (urgency_norm * 0.2)


print(f"Ranking {len(found_pairs)} pairs by composite score...")
print("  Weights: ROI 60% | Match Quality 20% | Time Urgency 20%")

for pair in found_pairs:
    pair['_score'] = compute_composite_score(pair)

found_pairs.sort(key=lambda p: p['_score'], reverse=True)
found_pairs = found_pairs[:TOP_N]

# Strip internal score key before sending
for pair in found_pairs:
    pair.pop('_score', None)

print(f"\n=== TOP {len(found_pairs)} OPPORTUNITIES ===")
for i, p in enumerate(found_pairs[:10], 1):
    ma_title = p['marketA'].get('title', '?')
    mb_title = p['marketB'].get('title', '?')
    end_a = str(p['marketA'].get('endDate', 'N/A'))[:10]
    print(f"  #{i}: {p.get('roi',0):.2f}% ROI | {p.get('matchScore',0)}% match | Ends: {end_a}")
    print(f"       A: {ma_title}")
    print(f"       B: {mb_title}")
print(f"  ... and {max(0, len(found_pairs) - 10)} more")
