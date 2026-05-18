"""
Run this script LOCALLY (on your own machine, not the server).

It opens a real headed Chromium browser, navigates to Colab, and waits for
you to log in manually.  Once you're logged in and the Colab home page has
loaded, press Enter in this terminal — the script saves state.json and prints
the curl command to upload it to your server.

Requirements (install once):
    pip install playwright
    playwright install chromium

Usage:
    python local_colab_auth.py [ngrok-url]

    ngrok-url  — your ngrok public URL, e.g.
                 https://copyrightable-pseudocartilaginous-sade.ngrok-free.dev
                 (defaults to that URL if omitted)
"""

import asyncio
import json
import sys
from pathlib import Path

STATE_FILE = Path("colab_state.json")
DEFAULT_NGROK = "https://copyrightable-pseudocartilaginous-sade.ngrok-free.dev"


async def main():
    ngrok_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else DEFAULT_NGROK

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed.\nRun:  pip install playwright && playwright install chromium")
        return

    print("Opening headed Chromium → Colab login page...")
    print("Log in with your Google account in the browser window that appears.")
    print("When the Colab home page has fully loaded, come back here and press Enter.\n")

    async with async_playwright() as pw:
        # headed=True so the user can interact
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        await page.goto("https://colab.research.google.com", wait_until="domcontentloaded")

        input(">>> Press Enter once you're logged into Colab... ")

        # Save full storage state (cookies + localStorage)
        await context.storage_state(path=str(STATE_FILE))
        await browser.close()

    size_kb = STATE_FILE.stat().st_size // 1024
    print(f"\n✓ Saved {STATE_FILE} ({size_kb} KB)")
    print("\nNow upload it to your server with this command:\n")
    print(f'  curl -X POST {ngrok_url}/colab-setup/upload-state \\')
    print(f'       -F "state=@{STATE_FILE}"\n')
    print("Or visit the setup page and use the upload form:")
    print(f"  {ngrok_url}/colab-setup\n")


asyncio.run(main())
