"""
LLM-based arbitrage verifier using a local Ollama instance.

Loads two concurrent workers running gemma4:31b-cloud to perform natural-language
verification of fuzzy-matched market pairs returned by Colab.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
OLLAMA_WORKERS = int(os.getenv("OLLAMA_WORKERS", "2"))

_PROMPT_TEMPLATE = """\
You are an expert prediction-market arbitrage analyst.

Market A (platform: {platform_a}): "{title_a}"
  YES price: {yes_a:.3f}

Market B (platform: {platform_b}): "{title_b}"
  YES price: {yes_b:.3f}

Computed ROI if arbitrage: {roi:.2f}%

Question: Do these two markets describe the EXACT SAME real-world event or outcome,
such that buying opposite sides creates a risk-free profit?

Reply ONLY with valid JSON — no markdown, no explanation outside JSON:
{{"is_arb": true_or_false, "confidence": 0_to_100, "reasoning": "one concise sentence"}}
"""


def verify_pair(pair: Dict[str, Any]) -> Dict[str, Any]:
    ma = pair.get("marketA", {})
    mb = pair.get("marketB", {})

    prompt = _PROMPT_TEMPLATE.format(
        platform_a=ma.get("platform", "?"),
        title_a=ma.get("title", ""),
        yes_a=float(ma.get("yesPrice", 0.5)),
        platform_b=mb.get("platform", "?"),
        title_b=mb.get("title", ""),
        yes_b=float(mb.get("yesPrice", 0.5)),
        roi=float(pair.get("roi", 0)),
    )

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120.0,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "{}")
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end]) if start >= 0 else {}
        pair["llm_is_arb"] = bool(parsed.get("is_arb", False))
        pair["llm_confidence"] = int(parsed.get("confidence", 0))
        pair["llm_reasoning"] = str(parsed.get("reasoning", ""))
    except Exception as e:
        logger.warning(f"Ollama error for pair ({ma.get('title','')[:40]}): {e}")
        pair["llm_is_arb"] = None
        pair["llm_confidence"] = 0
        pair["llm_reasoning"] = f"error: {e}"

    return pair


def run_llm_verification(
    opportunities: List[Dict[str, Any]],
    workers: int = OLLAMA_WORKERS,
) -> List[Dict[str, Any]]:
    """
    Verify all opportunities using two concurrent Ollama workers.
    Returns list sorted by (llm_is_arb desc, llm_confidence desc, roi desc).
    """
    logger.info(
        f"Starting LLM verification of {len(opportunities)} pairs "
        f"with model={OLLAMA_MODEL}, workers={workers}"
    )

    results: List[Dict[str, Any]] = [None] * len(opportunities)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {
            pool.submit(verify_pair, opp): i
            for i, opp in enumerate(opportunities)
        }
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = opportunities[idx]
                results[idx]["llm_reasoning"] = f"worker error: {e}"
            completed += 1
            if completed % 200 == 0 or completed == len(opportunities):
                logger.info(f"LLM progress: {completed}/{len(opportunities)}")

    confirmed = sum(1 for r in results if r and r.get("llm_is_arb"))
    logger.info(f"LLM verification complete: {confirmed}/{len(results)} confirmed arbitrage pairs.")

    return sorted(
        [r for r in results if r],
        key=lambda x: (
            x.get("llm_is_arb") or False,
            x.get("llm_confidence", 0),
            x.get("roi", 0),
        ),
        reverse=True,
    )
