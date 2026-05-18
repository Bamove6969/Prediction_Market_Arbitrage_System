import asyncio
import logging
import json
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

async def verify_match_with_llm(title_a: str, title_b: str, model: str = "qwen3.6:35b") -> Dict[str, Any]:
    """Uses Ollama to determine if two market titles refer to the same event."""
    prompt = f"""Title A: "{title_a}"
Title B: "{title_b}"

Are these prediction markets about the SAME event? Answer: YES or NO. Confidence: 0-100. Why:"""

    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "run", model, prompt,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        result = stdout.decode().strip()
        
        result_upper = result.upper()
        is_match = "YES" in result_upper
        conf_match = re.search(r"CONFIDENCE[:\s]*(\d+)", result, re.IGNORECASE)
        confidence = int(conf_match.group(1)) if conf_match else (90 if is_match else 10)
        
        return {
            "is_exact_match": is_match,
            "confidence": confidence,
            "reasoning": result[:200]
        }
    except Exception as e:
        logger.warning(f"LLM verification failed: {e}")
        return {"is_exact_match": False, "confidence": 0, "reasoning": str(e)}


async def verify_matches_with_llm(
    matches: List[Dict[str, Any]], 
    model: str = "qwen3.6:35b",
    max_workers: int = 4
) -> List[Dict[str, Any]]:
    """Verifies a batch of matches using Ollama LLM in parallel."""
    
    logger.info(f"Starting LLM verification on {len(matches)} matches with {model}...")
    
    semaphore = asyncio.Semaphore(max_workers)
    
    async def verify_one(match: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            title_a = match.get("marketA", {}).get("title", "")
            title_b = match.get("marketB", {}).get("title", "")
            result = await verify_match_with_llm(title_a, title_b, model)
            return {**match, **result}
    
    tasks = [verify_one(m) for m in matches]
    verified = await asyncio.gather(*tasks)
    
    # Filter to only high-confidence exact matches
    exact_matches = [
        v for v in verified 
        if v.get("is_exact_match", False) and v.get("confidence", 0) >= 85
    ]
    
    # Add sorting by soonest end date
    for m in exact_matches:
        end_a = m.get("marketA", {}).get("endDate") or "9999-12-31"
        end_b = m.get("marketB", {}).get("endDate") or "9999-12-31"
        m["earliestEndDate"] = min(end_a, end_b)
    
    exact_matches.sort(key=lambda x: (x["earliestEndDate"], -x.get("roi", 0)))
    
    logger.info(f"LLM verification complete. {len(exact_matches)} exact matches out of {len(matches)}")
    
    return exact_matches


def get_llm_verified_matches() -> List[Dict[str, Any]]:
    """Returns cached LLM-verified matches."""
    return _llm_verified_matches


_llm_verified_matches: List[Dict[str, Any]] = []
_verification_lock = asyncio.Lock()


async def run_llm_verification(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Main entry point to run LLM verification on matches."""
    global _llm_verified_matches
    
    async with _verification_lock:
        verified = await verify_matches_with_llm(matches)
        _llm_verified_matches = verified
        return verified