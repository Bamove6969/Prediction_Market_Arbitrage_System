"""
Full arbitrage pipeline orchestrator.

Startup sequence:
  1. ibga-trading ready (IBKR gateway)
  2. Backend up, auto-scan explicitly OFF
  3. Fetch Predicit + Polymarket + IBKR pass-1 concurrently
  4. IBKR pass-2 (TWS pricing) — next steps wait for this
  5. While scans run: pull Ollama models + configure ngrok in background
  6. ngrok 2-way tunnel established
  7. Latest notebook auto-uploaded to Google Drive + executed on Colab
  8. Colab pulls markets via ngrok, reduces to 2000 fuzzy matches, POSTs back
  9. Dual-model Ollama NL processing (gemma4:31b-cloud + qwen2.5:32b, 2 workers each)
 10. Final ranked report generated (HTML + JSON) with full questions, URLs, prices
"""

import asyncio
import json
import logging
import os
import sys
import time
import subprocess
import httpx
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("orchestrator")

# ── config ────────────────────────────────────────────────────────────────────
IBKR_HOST        = os.getenv("IBKR_HOST", "ibga")
IBKR_PORT        = int(os.getenv("IBKR_PORT", "4001"))
BACKEND_URL      = os.getenv("BACKEND_URL", "http://localhost:8000")
OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL_PRIMARY    = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
MODEL_SECONDARY  = os.getenv("OLLAMA_MODEL_2", "qwen2.5:32b")
OLLAMA_WORKERS   = int(os.getenv("OLLAMA_WORKERS", "2"))
NGROK_AUTHTOKEN  = os.getenv("NGROK_AUTHTOKEN", "")
NGROK_API        = "http://localhost:4040"

# Google / Colab
GOOGLE_CREDENTIALS_JSON  = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
COLAB_NOTEBOOK_DRIVE_ID  = os.getenv("COLAB_NOTEBOOK_DRIVE_ID", "")
GOOGLE_REFRESH_TOKEN     = os.getenv("GOOGLE_REFRESH_TOKEN", "")
GOOGLE_CLIENT_ID         = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET     = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Look for notebooks in both the image-baked dir and the bind-mounted project dir
_script_dir   = Path(__file__).parent
_project_dir  = Path("/app/project")
NOTEBOOK_DIR  = _project_dir if _project_dir.exists() else _script_dir
OUTPUT_DIR    = Path("/mnt/shared/Download")


# ══════════════════════════════════════════════════════════════════════════════
# 1. IBKR gateway readiness
# ══════════════════════════════════════════════════════════════════════════════

async def wait_for_ibkr_gateway(timeout: int = 300) -> bool:
    logger.info(f"Waiting for IBKR gateway at {IBKR_HOST}:{IBKR_PORT}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(IBKR_HOST, IBKR_PORT), timeout=5
            )
            w.close(); await w.wait_closed()
            logger.info("IBKR gateway ready.")
            return True
        except Exception:
            await asyncio.sleep(5)
    logger.error("IBKR gateway not ready after %ds.", timeout)
    return False


async def wait_for_backend(timeout: int = 120) -> bool:
    logger.info("Waiting for arbitrage backend...")
    deadline = time.time() + timeout
    async with httpx.AsyncClient(timeout=5) as client:
        while time.time() < deadline:
            try:
                r = await client.get(f"{BACKEND_URL}/api/health")
                if r.status_code == 200:
                    logger.info("Backend ready.")
                    return True
            except Exception:
                pass
            await asyncio.sleep(3)
    logger.error("Backend not ready.")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# 2. Auto-scan OFF + market fetches
# ══════════════════════════════════════════════════════════════════════════════

async def ensure_auto_scan_off():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{BACKEND_URL}/api/scanner-config", json={"enabled": False})
            logger.info("Auto-scan confirmed OFF.")
    except Exception as e:
        logger.warning(f"Could not disable auto-scan: {e}")


async def fetch_predicit() -> list:
    from backend.fetchers.predictit import fetch_predictit_markets
    markets = await fetch_predictit_markets()
    logger.info(f"Predicit: {len(markets)} markets")
    return markets


async def fetch_polymarket() -> list:
    from backend.fetchers.polymarket import fetch_polymarket_markets
    markets = await fetch_polymarket_markets(limit=50000)
    logger.info(f"Polymarket: {len(markets)} markets")
    return markets


async def fetch_ibkr(pass_num: int) -> list:
    from backend.fetchers.ibkr import fetch_ibkr_markets
    logger.info(f"IBKR pass {pass_num} starting...")
    markets = await fetch_ibkr_markets(
        on_progress=lambda msg: logger.info(f"  IBKR pass {pass_num}: {msg}")
    )
    logger.info(f"IBKR pass {pass_num}: {len(markets)} markets")
    return markets


async def push_markets_to_backend(markets: list):
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{BACKEND_URL}/api/ingest-markets", json=markets)
            r.raise_for_status()
            logger.info(f"Pushed {len(markets)} markets to backend.")
    except Exception as e:
        logger.warning(f"Market push skipped ({e}) — scanner DB already has them.")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Background: Ollama model pull + ngrok setup
# ══════════════════════════════════════════════════════════════════════════════

async def pull_ollama_models():
    for model in [MODEL_PRIMARY, MODEL_SECONDARY]:
        logger.info(f"Pulling Ollama model: {model}")
        try:
            async with httpx.AsyncClient(timeout=1800) as client:
                r = await client.post(
                    f"{OLLAMA_URL}/api/pull",
                    json={"name": model, "stream": False},
                )
                r.raise_for_status()
                logger.info(f"Model ready: {model}")
        except Exception as e:
            logger.error(f"Failed to pull {model}: {e}")


def start_ngrok(port: int = 8000) -> str:
    # 1. Try the sidecar ngrok container's local API (bound to 0.0.0.0:4040)
    sidecar_api = "http://ngrok:4040"
    for _ in range(20):
        try:
            resp = httpx.get(f"{sidecar_api}/api/tunnels", timeout=5)
            for t in resp.json().get("tunnels", []):
                url = t.get("public_url", "")
                if url.startswith("https://"):
                    logger.info(f"ngrok URL (sidecar): {url}")
                    return url
        except Exception:
            pass
        time.sleep(3)

    # 2. Fallback: env var NGROK_PUBLIC_URL (pre-configured known URL)
    known_url = os.getenv("NGROK_PUBLIC_URL", "").strip()
    if known_url.startswith("https://"):
        logger.info(f"ngrok URL (env override): {known_url}")
        return known_url

    # 3. Last resort: launch ngrok in-process
    logger.warning("ngrok sidecar not reachable, launching in-process...")
    if NGROK_AUTHTOKEN:
        subprocess.run(["ngrok", "authtoken", NGROK_AUTHTOKEN],
                       check=True, capture_output=True)
    subprocess.Popen(
        ["ngrok", "http", str(port), "--log=stdout"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(5)
    for _ in range(15):
        try:
            resp = httpx.get(f"{NGROK_API}/api/tunnels", timeout=5)
            for t in resp.json().get("tunnels", []):
                url = t.get("public_url", "")
                if url.startswith("https://"):
                    logger.info(f"ngrok URL (local): {url}")
                    return url
        except Exception:
            pass
        time.sleep(2)

    raise RuntimeError("Could not get ngrok public URL.")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Notebook upload + Colab execution
# ══════════════════════════════════════════════════════════════════════════════

def find_latest_notebook() -> Path:
    # Exclude _ready_* files (previously patched outputs) to avoid prefix stacking.
    candidates = [p for p in NOTEBOOK_DIR.glob("*.ipynb") if not p.name.startswith("_ready_")]
    if not candidates:
        raise FileNotFoundError("No .ipynb file found.")
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    logger.info(f"Latest notebook: {latest.name}")
    return latest


def patch_notebook(notebook_path: Path, ngrok_url: str) -> Path:
    with open(notebook_path) as f:
        nb = json.load(f)
    for cell in nb["cells"]:
        new_src = []
        for line in cell.get("source", []):
            if "LOCAL_BACKEND_URL" in line and '= "' in line:
                new_src.append(f'LOCAL_BACKEND_URL = "{ngrok_url}/api"\n')
            else:
                new_src.append(line)
        cell["source"] = new_src
    out = NOTEBOOK_DIR / f"_ready_{notebook_path.name}"
    with open(out, "w") as f:
        json.dump(nb, f, indent=2)
    logger.info(f"Notebook patched: {out.name}")
    return out


def _get_google_access_token() -> str | None:
    """Exchange refresh token for access token."""
    if not all([GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET]):
        return None
    try:
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": GOOGLE_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["access_token"]
    except Exception as e:
        logger.error(f"OAuth token refresh failed: {e}")
        return None


def upload_to_drive(notebook_path: Path, access_token: str) -> str | None:
    """Upload / update notebook in Google Drive. Returns file ID."""
    try:
        import mimetypes
        headers = {"Authorization": f"Bearer {access_token}"}

        if COLAB_NOTEBOOK_DRIVE_ID:
            # Update existing file
            url = f"https://www.googleapis.com/upload/drive/v3/files/{COLAB_NOTEBOOK_DRIVE_ID}?uploadType=media"
            with open(notebook_path, "rb") as f:
                r = httpx.patch(url, headers={**headers, "Content-Type": "application/json"}, content=f.read(), timeout=60)
            r.raise_for_status()
            logger.info(f"Notebook updated in Drive (id={COLAB_NOTEBOOK_DRIVE_ID})")
            return COLAB_NOTEBOOK_DRIVE_ID
        else:
            # Create new file
            meta = json.dumps({"name": notebook_path.name, "mimeType": "application/vnd.google.colab"})
            with open(notebook_path, "rb") as nb_f:
                r = httpx.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                    headers=headers,
                    files={
                        "metadata": ("metadata", meta, "application/json; charset=UTF-8"),
                        "file": (notebook_path.name, nb_f, "application/json"),
                    },
                    timeout=60,
                )
            r.raise_for_status()
            file_id = r.json()["id"]
            logger.info(f"Notebook uploaded to Drive (new id={file_id}) — add this to COLAB_NOTEBOOK_DRIVE_ID")
            return file_id
    except Exception as e:
        logger.error(f"Drive upload failed: {e}")
        return None


def trigger_colab_execution(file_id: str, access_token: str) -> bool:
    """Attempt to trigger Colab notebook execution via API."""
    try:
        r = httpx.post(
            "https://colab.research.google.com/api/notebook/execute",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"fileId": file_id},
            timeout=30,
        )
        if r.status_code in (200, 202):
            logger.info("Colab execution triggered successfully.")
            return True
        logger.warning(f"Colab API returned {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.error(f"Colab execution trigger failed: {e}")

    # Fallback: print the link
    logger.info(
        f"\n{'='*60}\n"
        f"Colab auto-execution not available — open this URL and click Runtime > Run All:\n"
        f"https://colab.research.google.com/drive/{file_id}\n"
        f"{'='*60}"
    )
    return False


def upload_and_run_colab(notebook_path: Path) -> bool:
    access_token = _get_google_access_token()

    if not access_token and GOOGLE_CREDENTIALS_JSON:
        # Try service account
        try:
            import google.oauth2.service_account as sa
            from google.auth.transport.requests import Request
            creds = sa.Credentials.from_service_account_info(
                json.loads(GOOGLE_CREDENTIALS_JSON),
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            creds.refresh(Request())
            access_token = creds.token
        except Exception as e:
            logger.error(f"Service account auth failed: {e}")

    if not access_token:
        logger.warning(
            "No Google credentials — skipping auto-upload. "
            f"Manually open notebook: {notebook_path}"
        )
        return False

    file_id = upload_to_drive(notebook_path, access_token)
    if not file_id:
        return False
    return trigger_colab_execution(file_id, access_token)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Wait for Colab results
# ══════════════════════════════════════════════════════════════════════════════

async def wait_for_colab_results(timeout: int = 3600, poll: int = 15) -> list:
    logger.info(f"Waiting for Colab results (timeout {timeout}s)...")
    deadline = time.time() + timeout
    async with httpx.AsyncClient(timeout=10) as client:
        while time.time() < deadline:
            try:
                r = await client.get(f"{BACKEND_URL}/api/opportunities")
                opps = r.json()
                if opps:
                    logger.info(f"Received {len(opps)} opportunities from Colab.")
                    return opps
            except Exception:
                pass
            await asyncio.sleep(poll)
    logger.warning("Timed out waiting for Colab.")
    return []


# ══════════════════════════════════════════════════════════════════════════════
# 6. Dual-model Ollama processing
# ══════════════════════════════════════════════════════════════════════════════

_VERIFY_PROMPT = """\
You are a prediction-market arbitrage analyst. Two markets from different platforms have \
been identified as potential arbitrage pairs.

Platform A ({platform_a}): "{title_a}"
  YES: {yes_a:.1%}  NO: {no_a:.1%}

Platform B ({platform_b}): "{title_b}"
  YES: {yes_b:.1%}  NO: {no_b:.1%}

Computed ROI: {roi:.2f}%

Do these markets describe the SAME real-world event/outcome? If someone wins YES on one, \
do they necessarily win YES (or NO) on the other?

Reply ONLY with valid JSON:
{{"is_arb": true_or_false, "confidence": 0_to_100, "reasoning": "one concise sentence"}}"""


def _call_ollama(model: str, pair: dict) -> dict:
    ma, mb = pair.get("marketA", {}), pair.get("marketB", {})
    prompt = _VERIFY_PROMPT.format(
        platform_a=ma.get("platform", "?"),
        title_a=ma.get("title", ""),
        yes_a=float(ma.get("yesPrice", 0.5)),
        no_a=float(ma.get("noPrice", 0.5)),
        platform_b=mb.get("platform", "?"),
        title_b=mb.get("title", ""),
        yes_b=float(mb.get("yesPrice", 0.5)),
        no_b=float(mb.get("noPrice", 0.5)),
        roi=float(pair.get("roi", 0)),
    )
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        raw = r.json().get("response", "{}")
        s, e = raw.find("{"), raw.rfind("}") + 1
        result = json.loads(raw[s:e]) if s >= 0 else {}
        return {
            "llm_is_arb":    bool(result.get("is_arb", False)),
            "llm_confidence": int(result.get("confidence", 0)),
            "llm_reasoning": str(result.get("reasoning", "")),
            "llm_model":     model,
        }
    except Exception as exc:
        return {"llm_is_arb": None, "llm_confidence": 0,
                "llm_reasoning": f"error: {exc}", "llm_model": model}


def process_half(pairs: list, model: str, workers: int) -> list:
    results = [None] * len(pairs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_call_ollama, model, p): i for i, p in enumerate(pairs)}
        for i, (fut, idx) in enumerate(futures.items()):
            try:
                llm_data = fut.result()
            except Exception as exc:
                llm_data = {"llm_is_arb": None, "llm_confidence": 0,
                            "llm_reasoning": str(exc), "llm_model": model}
            results[idx] = {**pairs[idx], **llm_data}
            if (i + 1) % 100 == 0:
                logger.info(f"  [{model}] {i+1}/{len(pairs)}")
    return results


async def dual_model_process(opportunities: list) -> list:
    logger.info(f"Dual-model processing: {len(opportunities)} pairs")
    mid = len(opportunities) // 2
    first_half  = opportunities[:mid]
    second_half = opportunities[mid:]

    loop = asyncio.get_event_loop()
    # Run both halves concurrently (each blocks its thread pool)
    r1, r2 = await asyncio.gather(
        loop.run_in_executor(None, process_half, first_half,  MODEL_PRIMARY,   OLLAMA_WORKERS),
        loop.run_in_executor(None, process_half, second_half, MODEL_SECONDARY, OLLAMA_WORKERS),
    )

    all_results = r1 + r2
    confirmed = sum(1 for r in all_results if r.get("llm_is_arb"))
    logger.info(f"LLM done: {confirmed}/{len(all_results)} confirmed arbitrage pairs")

    return sorted(
        all_results,
        key=lambda x: (
            bool(x.get("llm_is_arb")),
            int(x.get("llm_confidence", 0)),
            float(x.get("roi", 0)),
        ),
        reverse=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 7. Report generation
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(results: list) -> Path:
    from backend.report_generator import build_html_report, build_json_report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = OUTPUT_DIR / f"arb_report_{ts}.json"
    html_path = OUTPUT_DIR / f"arb_report_{ts}.html"

    build_json_report(results, json_path)
    build_html_report(results, html_path)

    logger.info(f"Reports written:\n  JSON: {json_path}\n  HTML: {html_path}")
    return html_path


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    logger.info("=" * 70)
    logger.info("Prediction Market Arbitrage Pipeline — Starting")
    logger.info("=" * 70)

    # ── 1. Wait for dependencies ──────────────────────────────────────────────
    await asyncio.gather(
        wait_for_ibkr_gateway(),
        wait_for_backend(),
    )
    await ensure_auto_scan_off()

    # ── 2+3. Fetch all markets — Predicit & Polymarket + IBKR pass 1 in parallel
    logger.info("\n── Phase 1: Fetching markets ──")
    predicit_task  = asyncio.create_task(fetch_predicit())
    polymarket_task = asyncio.create_task(fetch_polymarket())
    ibkr_pass1_task = asyncio.create_task(fetch_ibkr(1))

    # Also start Ollama pulls + ngrok in background while fetches run
    ollama_task = asyncio.create_task(pull_ollama_models())

    predicit_markets, polymarket_markets, ibkr_pass1 = await asyncio.gather(
        predicit_task, polymarket_task, ibkr_pass1_task
    )

    # ── 4. IBKR pass 2 — MUST complete before proceeding ─────────────────────
    logger.info("\n── Phase 2: IBKR second search (waiting) ──")
    ibkr_pass2 = await fetch_ibkr(2)

    ibkr_markets = ibkr_pass2 if len(ibkr_pass2) >= len(ibkr_pass1) else ibkr_pass1
    logger.info(f"IBKR final: {len(ibkr_markets)} (pass1={len(ibkr_pass1)}, pass2={len(ibkr_pass2)})")

    if not ibkr_markets:
        logger.error(
            "IBKR returned 0 markets — TWS/Gateway is not connected. "
            "Complete IBKR 2FA and ensure no other session is active, then restart the orchestrator."
        )
        return

    all_markets = predicit_markets + polymarket_markets + ibkr_markets
    logger.info(f"Total markets: {len(all_markets)}")
    await push_markets_to_backend(all_markets)

    # Free market data from memory before launching the browser — critical on low-RAM systems.
    del all_markets, predicit_markets, polymarket_markets, ibkr_markets, ibkr_pass1, ibkr_pass2
    import gc; gc.collect()

    # ── 5. ngrok ─────────────────────────────────────────────────────────────
    logger.info("\n── Phase 3: ngrok tunnel ──")
    try:
        ngrok_url = start_ngrok(port=8000)
    except Exception as e:
        logger.error(f"ngrok failed: {e}")
        ngrok_url = BACKEND_URL

    # ── 6. Notebook: patch + upload + execute on Colab ────────────────────────
    logger.info("\n── Phase 4: Colab notebook ──")
    colab_done: asyncio.Event | None = None
    colab_browser_task: asyncio.Task | None = None
    try:
        nb_path  = find_latest_notebook()
        patched  = patch_notebook(nb_path, ngrok_url)
        upload_and_run_colab(patched)
        # Playwright automation: open Colab in headless browser and click Run All
        if COLAB_NOTEBOOK_DRIVE_ID:
            try:
                from colab_runner import run_colab_notebook
                logger.info("Launching headless browser to trigger Colab Run All...")
                # Run browser as a background task so it stays open during Phase 5.
                # The done_event signals it to close once results arrive.
                colab_done = asyncio.Event()
                colab_browser_task = asyncio.create_task(
                    run_colab_notebook(
                        COLAB_NOTEBOOK_DRIVE_ID,
                        done_event=colab_done,
                        keep_alive_seconds=3900,
                    )
                )
                # Give the browser enough time to load and trigger Run All before
                # Phase 5 starts polling.
                await asyncio.sleep(90)
                if colab_browser_task.done() and not colab_browser_task.result():
                    logger.warning(
                        "Browser automation failed — open manually:\n"
                        f"https://colab.research.google.com/drive/{COLAB_NOTEBOOK_DRIVE_ID}"
                    )
                else:
                    logger.info("Colab Run All triggered via browser automation.")
            except Exception as e:
                logger.warning(
                    f"Colab browser automation error: {e}\n"
                    f"Open manually: https://colab.research.google.com/drive/{COLAB_NOTEBOOK_DRIVE_ID}"
                )
                colab_done = None
                colab_browser_task = None
    except Exception as e:
        logger.error(f"Notebook step error: {e}")
        colab_done = None
        colab_browser_task = None

    # Wait for Ollama pulls to finish before we need them
    logger.info("\n── Waiting for Ollama model pulls to finish ──")
    await ollama_task

    # ── 7. Wait for Colab to POST results back ────────────────────────────────
    logger.info("\n── Phase 5: Waiting for Colab results (up to 60 min) ──")
    opportunities = await wait_for_colab_results(timeout=7200)

    # Signal the browser to close now that results are in (or timed out)
    if colab_done is not None:
        colab_done.set()
    if colab_browser_task is not None and not colab_browser_task.done():
        await colab_browser_task

    if not opportunities:
        logger.warning("No Colab results received. Exiting.")
        return

    # ── 8. Dual-model Ollama NL processing ───────────────────────────────────
    logger.info(f"\n── Phase 6: Dual-model LLM processing ({MODEL_PRIMARY} + {MODEL_SECONDARY}) ──")
    final_results = await dual_model_process(opportunities)

    # ── 9. Report ─────────────────────────────────────────────────────────────
    logger.info("\n── Phase 7: Generating report ──")
    report_path = generate_report(final_results)

    # Push top verified results back to dashboard
    try:
        verified = [r for r in final_results if r.get("llm_is_arb")]
        async with httpx.AsyncClient(timeout=60) as client:
            await client.post(
                f"{BACKEND_URL}/api/cloud-results?clear=true",
                json=verified[:500],
            )
        logger.info(f"Pushed {len(verified)} confirmed pairs to dashboard.")
    except Exception as e:
        logger.error(f"Dashboard push failed: {e}")

    logger.info(f"\n{'='*70}")
    logger.info(f"Pipeline complete. Report: {report_path}")
    logger.info(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
