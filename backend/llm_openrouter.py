"""
OpenRouter LLM Worker - Replaces Ollama with OpenRouter API
Supports 2 models x 2 workers = 4 parallel workers
"""
import asyncio
import logging
import os
from typing import List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODELS = {
    "gemma": "google/gemma-4-31b-it:free",
    "nemotron": "nvidia/nemotron-3-super-120b-a12b:free",
}

class OpenRouterWorker:
    """Individual LLM worker that processes matches via OpenRouter"""
    
    def __init__(self, worker_id: str, model_key: str, batch_size: int = 500):
        self.worker_id = worker_id
        self.model_key = model_key
        self.model = MODELS.get(model_key, MODELS["qwen"])
        self.batch_size = batch_size
        self.api_url = f"{OPENROUTER_BASE_URL}/chat/completions"
        self.processed_count = 0
        self.matches_found = 0
    
    async def call_api(self, prompt: str) -> Dict[str, Any]:
        """Call OpenRouter API"""
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "Arbitrage Scanner"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(self.api_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "model": data.get("model", self.model)
                }
            except Exception as e:
                logger.error(f"OpenRouter API error: {e}")
                return {"content": "", "error": str(e)}
    
    async def verify_match(self, market_a: Dict, market_b: Dict) -> Dict[str, Any]:
        """Check if two markets match using LLM"""
        prompt = f"""Title A: "{market_a.get('title', '')}"
Title B: "{market_b.get('title', '')}"

Are these prediction markets about the SAME event? Answer YES or NO. Confidence: 0-100. Why:"""
        
        result = await self.call_api(prompt)
        
        content = result.get("content", "").upper()
        is_match = "YES" in content
        
        import re
        conf_match = re.search(r"CONFIDENCE[:\s]*(\d+)", result.get("content", ""), re.IGNORECASE)
        confidence = int(conf_match.group(1)) if conf_match else (90 if is_match else 10)
        
        return {
            "is_match": is_match,
            "confidence": confidence,
            "reasoning": result.get("content", "")[:200],
            "model": self.model
        }


class OpenRouterWorkerPool:
    """Pool of workers - 2 models x 2 workers = 4 parallel"""
    
    def __init__(self, num_workers_per_model: int = 2):
        self.workers = []
        
        for model_key in ["gemma", "nemotron"]:
            for i in range(num_workers_per_model):
                worker = OpenRouterWorker(
                    worker_id=f"{model_key}_worker_{i}",
                    model_key=model_key,
                    batch_size=500
                )
                self.workers.append(worker)
        
        logger.info(f"Created {len(self.workers)} OpenRouter workers: {[w.worker_id for w in self.workers]}")
    
    async def process_batch(self, matches: List[Dict]) -> List[Dict]:
        """Process matches in parallel across all workers"""
        logger.info(f"Processing {len(matches)} matches with {len(self.workers)} workers...")
        
        semaphore = asyncio.Semaphore(len(self.workers))
        
        async def process_one(match: Dict) -> Dict:
            async with semaphore:
                worker = self.workers[hash(str(match)) % len(self.workers)]
                market_a = match.get("marketA", {})
                market_b = match.get("marketB", {})
                
                result = await worker.verify_match(market_a, market_b)
                worker.processed_count += 1
                
                if result["is_match"] and result["confidence"] >= 85:
                    worker.matches_found += 1
                    return {**match, **result}
                return None
        
        tasks = [process_one(m) for m in matches]
        results = await asyncio.gather(*tasks)
        
        verified = [r for r in results if r is not None]
        
        for w in self.workers:
            logger.info(f"Worker {w.worker_id}: processed {w.processed_count}, found {w.matches_found} matches")
        
        return verified


async def verify_matches_openrouter(
    matches: List[Dict],
    num_workers: int = 2
) -> List[Dict]:
    """Main entry point - use this instead of verify_matches_with_llm"""
    pool = OpenRouterWorkerPool(num_workers_per_model=num_workers)
    return await pool.process_batch(matches)
