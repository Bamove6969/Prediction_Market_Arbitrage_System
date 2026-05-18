import json
import os

NOTEBOOK_PATH = 'Cloud_GPU_Matcher.ipynb'

if not os.path.exists(NOTEBOOK_PATH):
    print(f"Error: {NOTEBOOK_PATH} not found.")
    exit(1)

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# 1. Update Setup Cell
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and '!pip install' in ''.join(cell['source']):
        cell['source'] = [
            "# 1. Install required packages\n",
            "!pip install sentence-transformers torch httpx pydantic -q\n",
            "\n",
            "import torch\n",
            "from sentence_transformers import SentenceTransformer, CrossEncoder, util\n",
            "import httpx\n",
            "import asyncio\n",
            "from typing import List, Dict, Any\n",
            "import time\n",
            "\n",
            "print(f\"GPU Available: {torch.cuda.is_available()}\")\n",
            "if torch.cuda.is_available():\n",
            "    print(f\"GPU Device: {torch.cuda.get_device_name(0)}\")"
        ]
        print("Updated setup cell.")

# 2. Update Model Load Cell
for cell in nb['cells']:
    if 'metadata' in cell and cell['metadata'].get('id') == 'model_load':
        cell['source'] = [
            "# 2. Load ML Models directly onto the Cloud GPU\n",
            "print(\"Loading Bi-Encoder (Semantic Matrix)...\")\n",
            "bi_model = SentenceTransformer('all-MiniLM-L6-v2', device='cuda' if torch.cuda.is_available() else 'cpu')\n",
            "\n",
            "print(\"Loading Cross-Encoder (Nuance/Reasoning Engine)...\")\n",
            "cross_model = CrossEncoder('cross-encoder/nli-deberta-v3-small', device='cuda' if torch.cuda.is_available() else 'cpu')\n",
            "print(\"Models loaded successfully!\")"
        ]
        print("Updated model_load cell.")

# 3. Update Match Function Cell
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'def match_on_gpu(' in ''.join(cell['source']):
        cell['source'] = [
            "def get_key_numbers(text):\n",
            "    import re\n",
            "    parsed = set()\n",
            "    for n in re.findall(r'\\d+(?:\\.\\d+)?', text):\n",
            "        val = float(n)\n",
            "        if val not in (2024, 2025, 2026, 2027):\n",
            "            parsed.add(val)\n",
            "    return parsed\n\n",
            "# 4. Cloud GPU Matrix Multiplication Logic with CROSS-ENCODER (Nuance Detection)\n",
            "def compute_pair_arb(ma, mb):\n",
            "    price1_a, price1_b = ma['yesPrice'], 1 - mb['yesPrice']\n",
            "    price2_a, price2_b = 1 - ma['yesPrice'], mb['yesPrice']\n",
            "    \n",
            "    cost1 = price1_a + price1_b\n",
            "    roi1 = ((1 - cost1) / cost1 * 100) if cost1 < 1 and cost1 > 0 else -100\n",
            "    \n",
            "    cost2 = price2_a + price2_b\n",
            "    roi2 = ((1 - cost2) / cost2 * 100) if cost2 < 1 and cost2 > 0 else -100\n",
            "    \n",
            "    if roi1 > roi2:\n",
            "        return {\"roi\": roi1, \"cost\": cost1, \"scenario\": 1}\n",
            "    return {\"roi\": roi2, \"cost\": cost2, \"scenario\": 2}\n",
            "\n",
            "def match_on_gpu(markets, min_similarity=65.0, min_roi=0.1, top_k=2000):\n",
            "    by_platform = {}\n",
            "    for m in markets:\n",
            "        if m.get(\"isBinary\", True) and m.get(\"outcomeCount\", 2) == 2:\n",
            "            by_platform.setdefault(m[\"platform\"], []).append(m)\n",
            "            \n",
            "    platforms = list(by_platform.keys())\n",
            "    print(f\"Processing platforms: {platforms}\")\n",
            "    \n",
            "    # 1. Generate Embeddings on GPU (Bi-Encoder Phase)\n",
            "    start_time = time.time()\n",
            "    plat_embeddings = {}\n",
            "    for plat in platforms:\n",
            "        titles = [m[\"title\"] for m in by_platform[plat]]\n",
            "        print(f\"Encoding {len(titles)} markets for {plat}...\")\n",
            "        plat_embeddings[plat] = bi_model.encode(titles, convert_to_tensor=True, batch_size=256)\n",
            "        \n",
            "    # 2. Candidate Search (Fast Matrix Mul)\n",
            "    candidates = []\n",
            "    threshold_tensor = min_similarity / 100.0\n",
            "    \n",
            "    print(\"\\nExecuting Bi-Encoder Matrix Multiplications (Fast Filters)...\")\n",
            "    for i in range(len(platforms)):\n",
            "        pa = platforms[i]\n",
            "        emb_a = plat_embeddings[pa]\n",
            "        if emb_a is None: continue\n",
            "        \n",
            "        for j in range(i + 1, len(platforms)):\n",
            "            pb = platforms[j]\n",
            "            emb_b = plat_embeddings[pb]\n",
            "            if emb_b is None: continue\n",
            "            \n",
            "            cosine_scores = util.cos_sim(emb_a, emb_b)\n",
            "            high_score_indices = (cosine_scores >= threshold_tensor).nonzero(as_tuple=False)\n",
            "            \n",
            "            for idx in high_score_indices:\n",
            "                idx_a, idx_b = idx[0].item(), idx[1].item()\n",
            "                ma, mb = by_platform[pa][idx_a], by_platform[pb][idx_b]\n",
            "                \n",
            "                # --- NUMERICAL CONFLICT FILTER ---\n",
            "                nums_a = get_key_numbers(ma['title'])\n",
            "                nums_b = get_key_numbers(mb['title'])\n",
            "                if nums_a and nums_b and nums_a.isdisjoint(nums_b):\n",
            "                    continue\n\n",
            "                arb_data = compute_pair_arb(ma, mb)\n",
            "                if arb_data[\"roi\"] >= min_roi:\n",
            "                    candidates.append((ma, mb, arb_data[\"roi\"]))\n",
            "    \n",
            "    # 3. Nuance Reranking (Cross-Encoder Phase)\n",
            "    if not candidates:\n",
            "        return []\n",
            "        \n",
            "    print(f\"\\nApplying Nuance Reranking (Cross-Encoder) to top {len(candidates)} candidates...\")\n",
            "    # We rerank the top 2000 bi-encoder matches to save time\n",
            "    candidates.sort(key=lambda x: x[2], reverse=True)\n",
            "    candidates_to_rerank = candidates[:2000]\n",
            "    \n",
            "    pairs_to_score = [[c[0]['title'], c[1]['title']] for c in candidates_to_rerank]\n",
            "    \n",
            "    cross_scores = cross_model.predict(pairs_to_score, show_progress_bar=True)\n",
            "    \n",
            "    final_pairs = []\n",
            "    for i, score in enumerate(cross_scores):\n",
            "        # ms-marco scores can be high, normalize to 0-1 range roughly or just use raw\n",
            "        ma, mb, roi = candidates_to_rerank[i]\n",
            "        final_pairs.append({\n",
            "            \"marketA\": ma, \n",
            "            \"marketB\": mb, \n",
            "            \"roi\": roi,\n",
            "            \"matchScore\": min(100.0, max(0.0, float(score) * 10.0)), # Map logit to 0-100\n",
            "            \"isVerified\": True if score > 5.0 else False\n",
            "        })\n",
            "    \n",
            "    # 4. Sort by THE ABSOLUTE BEST (Confidence x ROI)\n",
            "    final_pairs.sort(key=lambda x: (x[\"isVerified\"], x[\"roi\"]), reverse=True)\n",
            "    \n",
            "    # Limit to Top 200 as requested\n",
            "    final_pairs = final_pairs[:top_k]\n",
            "    \n",
            "    end_time = time.time()\n",
            "    print(f\"\\nML Nuance Discovery Complete! Verified the absolute best {len(final_pairs)} matches in {end_time - start_time:.2f} seconds.\")\n",
            "    return final_pairs\n"
        ]
        print("Updated match_on_gpu function.")

# 4. Update the Run Call to include min_roi=0.1
for cell in nb['cells']:
    if 'found_pairs = match_on_gpu' in ''.join(cell['source']):
        cell['source'] = [
            "if all_markets:\n",
            "    # 2000 fuzzy matches for LLM validation\n",
            "    found_pairs = match_on_gpu(all_markets, min_similarity=55.0, min_roi=0.1, top_k=2000)\n",
            "else:\n",
            "    print(\"No markets loaded to process.\")"
        ]

with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Successfully injected Nuance Engine into Cloud_GPU_Matcher.ipynb.")
