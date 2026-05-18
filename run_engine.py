"""
Arbitrage Engine - Continuous Opportunity Monitor
Polls the backend scanner API and prints live arbitrage opportunities to the terminal.
The actual scanning/matching is handled by the FastAPI backend (backend/main.py).
"""
import time
import requests

API_BASE = "http://127.0.0.1:8000"
POLL_INTERVAL = 10  # seconds between status checks

print("=" * 55)
print("   ARBITRAGE ENGINE RUNNING")
print("   Monitoring backend for opportunities...")
print(f"   Polling every {POLL_INTERVAL}s | API: {API_BASE}")
print("=" * 55)

consecutive_errors = 0

while True:
    try:
        # Check scan status
        status_resp = requests.get(f"{API_BASE}/api/scan-status", timeout=30)
        status = status_resp.json()

        # --- REAL-TIME REFRESH (fire-and-forget) ---
        # Kick off a background price update but don't wait for it —
        # the backend lock ensures only one refresh runs at a time.
        try:
            requests.post(f"{API_BASE}/api/refresh-leads?limit=20", timeout=60)
        except Exception:
            pass  # Non-fatal: stale prices are fine, next loop will retry

        # Fetch latest opportunities (uses whatever prices are currently cached)
        opps_resp = requests.get(f"{API_BASE}/api/arbitrage-opportunities?limit=10", timeout=30)
        opps = opps_resp.json()

        is_scanning = status.get("is_scanning", False)
        phase = status.get("phase", "idle")
        progress = status.get("progress", 0)
        pairs_found = status.get("pairs_found", 0)

        print(f"\n[{time.strftime('%H:%M:%S')}] Status: {'SCANNING' if is_scanning else 'IDLE'} | Phase: {phase} | Progress: {progress}% | Pairs: {pairs_found}")

        if opps and isinstance(opps, list):
            print(f"  Top Leads (Real-time Refreshed):")
            for o in opps[:8]:
                a = o.get("marketA", {})
                b = o.get("marketB", {})
                roi = o.get("roi", 0)
                score = o.get("matchScore", 0)
                
                # Color code ROI (basic terminal support)
                prefix = " [+] " if roi > 1.0 else " [ ] "
                print(f"{prefix}{roi:6.2f}% ROI | Match: {score:>3}% | {a.get('platform','?')} vs {b.get('platform','?')} | {a.get('title','?')[:60]}...")
        else:
            print("  No high-quality leads found yet. Check Colab sync status.")

        consecutive_errors = 0

    except requests.exceptions.ConnectionError:
        consecutive_errors += 1
        print(f"[{time.strftime('%H:%M:%S')}] Backend not reachable (attempt {consecutive_errors}). Is backend.main running on port 8000?")
    except requests.exceptions.Timeout:
        consecutive_errors += 1
        print(f"[{time.strftime('%H:%M:%S')}] Request timed out (attempt {consecutive_errors}) — backend may be busy refreshing prices.")
    except Exception as e:
        consecutive_errors += 1
        print(f"[{time.strftime('%H:%M:%S')}] Error: {e}")

    time.sleep(POLL_INTERVAL)