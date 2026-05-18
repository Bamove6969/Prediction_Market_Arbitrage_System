# 5. Enhanced Matching with NLI Cross-Encoder

def compute_pair_arb(ma, mb):
    price1_a, price1_b = ma['yesPrice'], 1 - mb['yesPrice']
    price2_a, price2_b = 1 - ma['yesPrice'], mb['yesPrice']
    
    cost1 = price1_a + price1_b
    roi1 = ((1 - cost1) / cost1 * 100) if cost1 < 1 and cost1 > 0 else -100
    
    cost2 = price2_a + price2_b
    roi2 = ((1 - cost2) / cost2 * 100) if cost2 < 1 and cost2 > 0 else -100
    
    if roi1 > roi2:
        return {"roi": roi1, "cost": cost1, "scenario": 1}
    return {"roi": roi2, "cost": cost2, "scenario": 2}

def match_on_gpu(markets, min_similarity=75.0, min_roi=0.1, top_k=200):
    by_platform = {}
    for m in markets:
        if m.get("isBinary", True) and m.get("outcomeCount", 2) == 2:
            by_platform.setdefault(m["platform"], []).append(m)
            
    platforms = list(by_platform.keys())
    print(f"Processing platforms: {platforms}")
    
    # 1. Generate Embeddings on GPU (Bi-Encoder Phase)
    start_time = time.time()
    plat_embeddings = {}
    for plat in platforms:
        titles = [m["title"] for m in by_platform[plat]]
        print(f"Encoding {len(titles)} markets for {plat}...")
        plat_embeddings[plat] = bi_model.encode(titles, convert_to_tensor=True, batch_size=256)
        
    # 2. Candidate Search (Fast Matrix Mul)
    candidates = []
    threshold_tensor = min_similarity / 100.0
    
    print("\nExecuting Bi-Encoder Matrix Multiplications (Fast Filters)...")
    filtered_by_dates = 0
    filtered_by_numbers = 0
    filtered_by_entities = 0
    filtered_by_temporal = 0
    
    for i in range(len(platforms)):
        pa = platforms[i]
        emb_a = plat_embeddings[pa]
        if emb_a is None: continue
        
        for j in range(i + 1, len(platforms)):
            pb = platforms[j]
            emb_b = plat_embeddings[pb]
            if emb_b is None: continue
            
            cosine_scores = util.cos_sim(emb_a, emb_b)
            high_score_indices = (cosine_scores >= threshold_tensor).nonzero(as_tuple=False)
            
            for idx in high_score_indices:
                idx_a, idx_b = idx[0].item(), idx[1].item()
                ma, mb = by_platform[pa][idx_a], by_platform[pb][idx_b]
                
                # --- ENHANCED COMPATIBILITY CHECK ---
                compatible, reason = are_questions_compatible(ma['title'], mb['title'])
                if not compatible:
                    if 'Date' in reason:
                        filtered_by_dates += 1
                    elif 'Number' in reason:
                        filtered_by_numbers += 1
                    elif 'Entity' in reason:
                        filtered_by_entities += 1
                    elif 'Temporal' in reason:
                        filtered_by_temporal += 1
                    continue

                arb_data = compute_pair_arb(ma, mb)
                if arb_data["roi"] >= min_roi:
                    candidates.append((ma, mb, arb_data["roi"], reason))
    
    print(f"\n📊 Filtering Stats:")
    print(f"  ❌ Filtered by date mismatch: {filtered_by_dates}")
    print(f"  ❌ Filtered by number mismatch: {filtered_by_numbers}")
    print(f"  ❌ Filtered by entity mismatch: {filtered_by_entities}")
    print(f"  ❌ Filtered by temporal conflict: {filtered_by_temporal}")
    print(f"  ✅ Candidates passed to NLI: {len(candidates)}")
    
    # 3. NLI Reranking (Entailment Detection)
    if not candidates:
        return []
        
    print(f"\nApplying NLI Cross-Encoder (Logical Equivalence Check)...")
    candidates.sort(key=lambda x: x[2], reverse=True)
    candidates_to_rerank = candidates[:2000]
    
    # NLI models expect pairs in format: [premise, hypothesis]
    pairs_to_score = [[c[0]['title'], c[1]['title']] for c in candidates_to_rerank]
    
    # NLI returns: [contradiction_score, neutral_score, entailment_score]
    nli_scores = cross_model.predict(pairs_to_score, show_progress_bar=True)
    
    final_pairs = []
    for i, scores in enumerate(nli_scores):
        ma, mb, roi, compat_reason = candidates_to_rerank[i]
        
        # Extract entailment score (index 2)
        # High entailment = questions are logically equivalent
        entailment_score = float(scores[2]) if len(scores) > 2 else float(scores)
        
        # Only keep pairs with strong entailment (>0.5 means more likely entailed than not)
        if entailment_score > 0.5:  # RAISED from 0.4 to be more strict
            final_pairs.append({
                "marketA": ma, 
                "marketB": mb, 
                "roi": roi,
                "matchScore": min(100.0, entailment_score * 100.0),
                "matchReason": f"NLI Entailment: {entailment_score:.3f} | {compat_reason}",
                "isVerified": entailment_score > 0.7  # High confidence
            })
    
    # 4. Sort by confidence and ROI
    final_pairs.sort(key=lambda x: (x["isVerified"], x["matchScore"], x["roi"]), reverse=True)
    
    # Limit to Top K
    final_pairs = final_pairs[:top_k]
    
    end_time = time.time()
    print(f"\n✅ Enhanced ML Discovery Complete!")
    print(f"   Found {len(final_pairs)} high-precision matches in {end_time - start_time:.2f}s")
    print(f"   Verified (>70% entailment): {sum(1 for p in final_pairs if p['isVerified'])}")
    return final_pairs

# Run the enhanced matcher
found_pairs = match_on_gpu(all_markets, min_similarity=75.0, min_roi=0.1, top_k=200)
