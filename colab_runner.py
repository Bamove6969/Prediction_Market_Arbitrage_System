"""
Playwright-based Google Colab automation.

Opens the Colab notebook headlessly, triggers Runtime → Run All, then keeps
the browser session alive until the orchestrator signals completion (via the
done_event) or the timeout expires.  Keeping the browser open is essential —
Colab disconnects the kernel when the controlling browser session ends.

Auth state is persisted at COLAB_AUTH_STATE (default /mnt/shared/colab_auth.json).
Do the one-time setup at /colab-setup before running the orchestrator.
"""

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

AUTH_STATE_PATH = Path(os.getenv("COLAB_AUTH_STATE", "/mnt/shared/colab_auth.json"))

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-setuid-sandbox",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-first-run",
    "--renderer-process-limit=1",
    "--js-flags=--max-old-space-size=192",
]


async def run_colab_notebook(
    notebook_id: str,
    done_event: asyncio.Event | None = None,
    keep_alive_seconds: int = 3900,
) -> bool:
    """
    Open the Colab notebook and trigger Run All.

    Keeps the browser open until done_event is set or keep_alive_seconds
    elapses — whichever comes first.  This prevents Colab from disconnecting
    the kernel when the browser session ends.

    Returns True if Run All was successfully triggered.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("playwright not installed")
        return False

    if not AUTH_STATE_PATH.exists():
        logger.warning(
            "No saved Colab auth state at %s. Visit <ngrok-url>/colab-setup first.",
            AUTH_STATE_PATH,
        )
        return False

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            storage_state=str(AUTH_STATE_PATH),
        )
        logger.info("Using saved Colab auth state from %s", AUTH_STATE_PATH)
        page = await context.new_page()

        try:
            colab_url = f"https://colab.research.google.com/drive/{notebook_id}"
            logger.info("Opening Colab: %s", colab_url)
            await page.goto(colab_url, wait_until="domcontentloaded", timeout=60_000)

            if "accounts.google.com" in page.url or "signin" in page.url.lower():
                logger.error(
                    "Redirected to Google login — auth state may be expired. "
                    "Re-import cookies at /colab-setup."
                )
                return False

            # Wait for notebook cells
            logger.info("Waiting for notebook cells to appear...")
            try:
                await page.wait_for_selector("colab-cell, .cell", timeout=30_000)
            except Exception:
                await page.wait_for_load_state("networkidle", timeout=30_000)

            # Refresh auth state while we're here
            AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(AUTH_STATE_PATH))

            # Trigger Runtime → Run All
            logger.info("Sending Ctrl+F9 (Run all)...")
            await page.keyboard.press("Control+F9")

            # Handle "Run anyway?" dialog
            for _ in range(6):
                await asyncio.sleep(2)
                try:
                    btn = page.get_by_role("button", name="Run anyway")
                    if await btn.is_visible(timeout=500):
                        await btn.click()
                        logger.info("Clicked 'Run anyway'")
                        break
                except Exception:
                    pass

            logger.info(
                "Run All triggered — keeping browser open to maintain Colab session "
                "(up to %ds or until results arrive).", keep_alive_seconds
            )

            # Keep the browser alive so Colab doesn't disconnect the kernel.
            # Periodically scroll the page to prevent idle disconnection.
            if done_event is None:
                done_event = asyncio.Event()

            elapsed = 0
            ping_interval = 30
            while elapsed < keep_alive_seconds and not done_event.is_set():
                await asyncio.sleep(ping_interval)
                elapsed += ping_interval
                try:
                    # Gentle scroll to signal activity to Colab
                    await page.evaluate("window.scrollBy(0, 1)")
                    await page.evaluate("window.scrollBy(0, -1)")
                except Exception:
                    pass
                if elapsed % 300 == 0:
                    logger.info("Colab session still open (%ds elapsed)...", elapsed)

            logger.info("Closing Colab browser session.")
            return True

        except Exception as exc:
            logger.error("Colab automation error: %s", exc)
            return False

        finally:
            await browser.close()


async def _google_login(page) -> bool:
    """Fill Google sign-in form — only needed if cookie auth fails."""
    email = os.getenv("GOOGLE_EMAIL", "")
    password = os.getenv("GOOGLE_PASSWORD", "")
    try:
        await page.wait_for_selector('input[type="email"]', timeout=15_000)
        await page.fill('input[type="email"]', email)
        await page.click("#identifierNext, button:has-text('Next')")
        await page.wait_for_selector('input[type="password"]', timeout=15_000)
        await page.fill('input[type="password"]', password)
        await page.click("#passwordNext, button:has-text('Next')")
        await page.wait_for_url(lambda url: "accounts.google.com" not in url, timeout=30_000)
        logger.info("Google login succeeded")
        return True
    except Exception as exc:
        logger.error("Google login failed: %s", exc)
        return False
