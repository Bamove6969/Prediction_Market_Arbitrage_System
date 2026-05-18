"""
/colab-setup  — one-time Google session import for Colab automation.

Google blocks headless browser sign-in.  Two supported methods:

Method A (recommended) — local_colab_auth.py:
  Run local_colab_auth.py on your own machine.  It opens a real headed
  Chromium browser, you log in manually, then it saves colab_state.json.
  Upload that file here via POST /colab-setup/upload-state or the web form.

Method B — Cookie-Editor JSON:
  1. Open https://colab.research.google.com while logged in
  2. Install "Cookie-Editor" extension → Export → "Export as JSON"
  3. Paste the JSON into the form at /colab-setup

Endpoints
---------
GET  /colab-setup                → HTML import page
POST /colab-setup/upload-state   → upload Playwright state.json file (Method A)
POST /colab-setup/import         → import cookie JSON (Method B)
GET  /colab-setup/status         → auth state info
GET  /colab-setup/verify         → test saved auth against Colab
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/colab-setup", tags=["colab-setup"])

AUTH_STATE_PATH = Path(os.getenv("COLAB_AUTH_STATE", "/app/data/colab_state.json"))

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
]

# ── HTML page ─────────────────────────────────────────────────────────────────
_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Colab Auth Setup</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 20px; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 24px; max-width: 720px; margin: 0 auto; }
h1 { font-size: 1.3rem; font-weight: 700; margin-bottom: 4px; }
.sub { color: #94a3b8; font-size: 0.85rem; margin-bottom: 24px; }
h2 { font-size: 0.9rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; margin-top: 20px; }
ol { padding-left: 20px; color: #cbd5e1; font-size: 0.88rem; line-height: 1.8; margin-bottom: 16px; }
ol li { margin-bottom: 4px; }
pre { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 10px 14px; font-size: 0.78rem; color: #7dd3fc; overflow-x: auto; margin-bottom: 16px; white-space: pre-wrap; word-break: break-all; }
code { background: #0f172a; padding: 1px 6px; border-radius: 4px; font-family: monospace; font-size: 0.85em; color: #7dd3fc; }
input[type=file] { display: block; width: 100%; margin-bottom: 12px; color: #cbd5e1; font-size: 0.85rem; }
textarea { width: 100%; height: 140px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; color: #e2e8f0; font-family: monospace; font-size: 0.8rem; resize: vertical; margin-bottom: 12px; }
textarea:focus, input[type=file]:focus { outline: none; }
button { padding: 10px 20px; border-radius: 8px; border: none; font-size: 0.9rem; font-weight: 600; cursor: pointer; width: 100%; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: #334155; color: #e2e8f0; margin-top: 8px; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.status { margin-top: 16px; padding: 12px 16px; border-radius: 8px; font-size: 0.85rem; display: none; }
.status.ok  { background: #14532d; color: #86efac; border: 1px solid #16a34a; display: block; }
.status.err { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; display: block; }
.status.info { background: #1e3a5f; color: #93c5fd; border: 1px solid #3b82f6; display: block; }
.divider { border: none; border-top: 1px solid #334155; margin: 24px 0; }
.badge { background: #1a2e1a; border: 1px solid #16a34a; border-radius: 8px; padding: 12px 16px; font-size: 0.85rem; color: #86efac; margin-bottom: 20px; }
.method-label { display: inline-block; background: #1e40af; color: #bfdbfe; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-bottom: 10px; letter-spacing: 0.05em; }
.method-b-label { background: #4b1d96; color: #ddd6fe; }
</style>
</head>
<body>
<div class="card">
  <h1>Colab Auth Setup</h1>
  <p class="sub">One-time setup — save your Google session so Colab runs automatically.</p>

  <div id="existing-badge" class="badge" style="display:none">
    ✓ Auth state already saved. Re-upload only if Colab stops working.
  </div>

  <!-- ── METHOD A ─────────────────────────────────────────── -->
  <span class="method-label">METHOD A — RECOMMENDED</span>
  <h2>Run local_colab_auth.py on your machine</h2>
  <ol>
    <li>On your <strong>own computer</strong>, install Playwright once:<br>
      <pre>pip install playwright
playwright install chromium</pre>
    </li>
    <li>Download <a href="/colab-setup/download-script" style="color:#7dd3fc">local_colab_auth.py</a> and run it:<br>
      <pre>python local_colab_auth.py</pre>
      A real browser window opens → log in with Google → press Enter in the terminal.
    </li>
    <li>The script saves <code>colab_state.json</code> and prints the upload command.
      Or upload it below:</li>
  </ol>

  <input type="file" id="state-file" accept=".json,application/json">
  <button class="btn-primary" id="upload-btn" onclick="uploadState()">Upload colab_state.json</button>
  <div id="status-a" class="status"></div>

  <hr class="divider">

  <!-- ── METHOD B ─────────────────────────────────────────── -->
  <span class="method-label method-b-label">METHOD B — COOKIE-EDITOR</span>
  <h2>Paste Cookie-Editor JSON export</h2>
  <ol>
    <li>Install <strong>Cookie-Editor</strong>
      (<a href="https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm" target="_blank" style="color:#7dd3fc">Chrome</a> /
       <a href="https://addons.mozilla.org/firefox/addon/cookie-editor/" target="_blank" style="color:#7dd3fc">Firefox</a>)</li>
    <li>Open <code>colab.research.google.com</code> while logged in</li>
    <li>Cookie-Editor icon → <strong>Export</strong> → <strong>Export as JSON</strong></li>
    <li>Paste below:</li>
  </ol>
  <textarea id="cookie-json" placeholder='[{"name":"__Secure-3PSID","value":"...","domain":".google.com",...}, ...]'></textarea>
  <button class="btn-secondary" id="import-btn" onclick="importCookies()">Import Cookies &amp; Verify</button>
  <div id="status-b" class="status"></div>

  <hr class="divider">
  <p style="font-size:0.78rem; color:#64748b">
    Your session is stored only on your server at <code>/mnt/shared/colab_auth.json</code>.
    It never leaves your infrastructure.
  </p>
</div>

<script>
async function checkExisting() {
  const r = await fetch('/colab-setup/status');
  const d = await r.json();
  if (d.auth_saved) document.getElementById('existing-badge').style.display = 'block';
}

async function uploadState() {
  const file = document.getElementById('state-file').files[0];
  if (!file) { showStatus('a', 'Select a colab_state.json file first.', 'err'); return; }
  const btn = document.getElementById('upload-btn');
  btn.disabled = true; btn.textContent = 'Uploading…';
  showStatus('a', 'Uploading and verifying…', 'info');
  try {
    const fd = new FormData();
    fd.append('state', file);
    const r = await fetch('/colab-setup/upload-state', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.ok) {
      showStatus('a', '✓ ' + d.message, 'ok');
      document.getElementById('existing-badge').style.display = 'block';
    } else {
      showStatus('a', '✗ ' + (d.detail || d.message || 'Upload failed'), 'err');
    }
  } catch (e) {
    showStatus('a', 'Network error: ' + e.message, 'err');
  } finally {
    btn.disabled = false; btn.textContent = 'Upload colab_state.json';
  }
}

async function importCookies() {
  const raw = document.getElementById('cookie-json').value.trim();
  if (!raw) { showStatus('b', 'Paste your cookie JSON first.', 'err'); return; }
  let cookies;
  try { cookies = JSON.parse(raw); }
  catch { showStatus('b', 'Invalid JSON — make sure you copied the full export.', 'err'); return; }
  const btn = document.getElementById('import-btn');
  btn.disabled = true; btn.textContent = 'Importing…';
  showStatus('b', 'Injecting cookies and verifying Colab access…', 'info');
  try {
    const r = await fetch('/colab-setup/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookies }),
    });
    const d = await r.json();
    if (d.ok) {
      showStatus('b', '✓ ' + d.message, 'ok');
      document.getElementById('existing-badge').style.display = 'block';
    } else {
      showStatus('b', '✗ ' + (d.detail || d.message || 'Import failed'), 'err');
    }
  } catch (e) {
    showStatus('b', 'Network error: ' + e.message, 'err');
  } finally {
    btn.disabled = false; btn.textContent = 'Import Cookies & Verify';
  }
}

function showStatus(method, msg, type) {
  const el = document.getElementById('status-' + method);
  el.textContent = msg; el.className = 'status ' + type;
}

checkExisting();
</script>
</body>
</html>"""


# ── Pydantic models ───────────────────────────────────────────────────────────

class ImportBody(BaseModel):
    cookies: list[dict[str, Any]]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def setup_page():
    return HTMLResponse(_HTML)


@router.post("/import")
async def import_cookies(body: ImportBody):
    """
    Receive cookies from Cookie-Editor JSON export, inject into a Playwright
    context, navigate to Colab to verify access, then save the auth state.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(500, "playwright not installed in this container")

    cookies = body.cookies
    if not cookies:
        raise HTTPException(400, "No cookies provided")

    logger.info("Importing %d cookies for Colab auth", len(cookies))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )

        # Override navigator.webdriver
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Normalise and inject cookies
        normalised = _normalise_cookies(cookies)
        await context.add_cookies(normalised)

        page = await context.new_page()

        # Navigate to Colab and check we're logged in (not redirected to sign-in)
        try:
            resp = await page.goto(
                "https://colab.research.google.com",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
        except Exception as exc:
            await browser.close()
            return {"ok": False, "message": f"Navigation failed: {exc}"}

        final_url = page.url
        if "accounts.google.com" in final_url or "signin" in final_url.lower():
            await browser.close()
            return {
                "ok": False,
                "message": (
                    "Still redirected to Google login — the cookies may be expired or incomplete. "
                    "Make sure you exported from colab.research.google.com while logged in."
                ),
            }

        # Looks good — save the auth state
        AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(AUTH_STATE_PATH))
        await browser.close()

        logger.info("Colab auth state saved to %s", AUTH_STATE_PATH)
        return {
            "ok": True,
            "message": (
                f"Colab access verified and auth state saved. "
                f"The orchestrator will now run Colab automatically on the next pipeline run."
            ),
        }


@router.post("/upload-state")
async def upload_state(state: UploadFile = File(...)):
    """
    Accept a Playwright storage_state JSON file (produced by local_colab_auth.py)
    and save it directly as the Colab auth state — no headless verification needed
    because the file already contains a real browser session.
    """
    try:
        raw = await state.read()
        data = json.loads(raw)
    except Exception as exc:
        return {"ok": False, "message": f"Invalid JSON: {exc}"}

    # Sanity-check: Playwright state.json has a 'cookies' key
    if "cookies" not in data:
        return {
            "ok": False,
            "message": (
                "File doesn't look like a Playwright state.json "
                "(missing 'cookies' key). Run local_colab_auth.py to generate it."
            ),
        }

    AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTH_STATE_PATH.write_bytes(raw)
    n_cookies = len(data.get("cookies", []))
    logger.info("Colab auth state uploaded (%d cookies) → %s", n_cookies, AUTH_STATE_PATH)
    return {
        "ok": True,
        "message": (
            f"Auth state saved ({n_cookies} cookies). "
            "The orchestrator will now trigger Colab automatically."
        ),
    }


@router.get("/download-script")
async def download_script():
    """Serve local_colab_auth.py for download."""
    from fastapi.responses import FileResponse
    script = Path(__file__).parent.parent / "local_colab_auth.py"
    if not script.exists():
        raise HTTPException(404, "local_colab_auth.py not found on server")
    return FileResponse(str(script), filename="local_colab_auth.py", media_type="text/x-python")


@router.get("/status")
async def status():
    return {
        "auth_saved": AUTH_STATE_PATH.exists(),
        "auth_path": str(AUTH_STATE_PATH),
    }


@router.get("/verify")
async def verify():
    """Quick headless check that saved auth still works against Colab."""
    if not AUTH_STATE_PATH.exists():
        return {"ok": False, "message": "No auth state saved yet — visit /colab-setup first"}

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(500, "playwright not installed")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        context = await browser.new_context(storage_state=str(AUTH_STATE_PATH))
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()
        await page.goto("https://colab.research.google.com", wait_until="domcontentloaded", timeout=20_000)
        url = page.url
        await browser.close()

    if "accounts.google.com" in url:
        return {"ok": False, "message": "Session expired — re-import cookies via /colab-setup"}
    return {"ok": True, "message": f"Colab auth valid (landed on {url})"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_cookies(raw: list[dict]) -> list[dict]:
    """
    Normalise Cookie-Editor JSON (Chrome or Firefox) to Playwright's format.

    Firefox-specific fields (hostOnly, firstPartyDomain, partitionKey, storeId,
    session) are silently dropped — Playwright doesn't accept them.

    Per the cookie spec, SameSite=None requires Secure=True; we enforce that
    here because Firefox exports some Google cookies with no_restriction + secure=false.
    """
    SAME_SITE_MAP = {
        "no_restriction": "None",
        "lax": "Lax",
        "strict": "Strict",
        "unspecified": "Lax",
        None: "Lax",
    }
    out = []
    for c in raw:
        name = c.get("name", "")
        domain = c.get("domain", "")
        if not name or not domain:
            continue
        same_site_raw = (c.get("sameSite") or c.get("same_site") or "lax").lower().replace(" ", "_")
        same_site = SAME_SITE_MAP.get(same_site_raw, "Lax")
        secure = bool(c.get("secure"))
        # SameSite=None is only valid on Secure cookies; enforce the spec so
        # Playwright doesn't reject the cookie silently.
        if same_site == "None":
            secure = True
        cookie: dict = {
            "name":     name,
            "value":    c.get("value", ""),
            "domain":   domain,
            "path":     c.get("path", "/"),
            "httpOnly": bool(c.get("httpOnly") or c.get("http_only")),
            "secure":   secure,
            "sameSite": same_site,
        }
        if c.get("expirationDate") or c.get("expires"):
            cookie["expires"] = int(c.get("expirationDate") or c.get("expires"))
        out.append(cookie)
    return out
