import httpx
import time
import sys

def check_status():
    try:
        r = httpx.get('http://localhost:8000/api/scan-status')
        data = r.json()
        pairs = data.get("pairs_found", 0)
        msg = data.get("message", "")
        return pairs, msg
    except Exception as e:
        return None, str(e)

print("Starting sync monitor...")
initial_pairs, initial_msg = check_status()
print(f"Initial: {initial_pairs} pairs | {initial_msg}")

# Wait up to 2 minutes for a change
for i in range(12):
    time.sleep(10)
    current_pairs, current_msg = check_status()
    if current_pairs is not None:
        if current_pairs != initial_pairs:
            print(f"UPDATE: {current_pairs} pairs (+{current_pairs - initial_pairs}) | {current_msg}")
            sys.exit(0)
        else:
            print(f"Polling... ({current_pairs} pairs)")

print("No change detected after 120s.")
