import asyncio
import json
import csv
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
from backend.database import get_db

logger = logging.getLogger(__name__)

DATASET_DIR = os.path.join(os.path.dirname(__file__), "datasets")

async def export_feedback_to_csv(filename: str = "feedback_training_data.csv"):
    """
    Exports the contents of the feedback table and optional synthetic negatives to a CSV file.
    """
    include_synthetic = True # Enable by default for better training
    if not os.path.exists(DATASET_DIR):
        os.makedirs(DATASET_DIR)
        
    filepath = os.path.join(DATASET_DIR, filename)
    db = await get_db()
    
    try:
        cursor = await db.execute("SELECT * FROM feedback")
        rows = await cursor.fetchall()
        
        if not rows:
            logger.info("No feedback data found to export.")
            return None
            
        with open(filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Header
            writer.writerow([
                "market_a_title", "market_b_title", 
                "match_score", "match_reason", "verdict"
            ])
            
            for row in rows:
                # Convert 'correct' -> 1, 'incorrect' -> 0 for training
                label = 1 if row["verdict"] == "correct" else 0
                writer.writerow([
                    row["market_a_title"], 
                    row["market_b_title"],
                    row["match_score"],
                    row["match_reason"],
                    label
                ])
                
        logger.info(f"Successfully exported {len(rows)} samples to {filepath}")
        
        if include_synthetic:
            synthetic_negatives = await generate_hard_negatives()
            if synthetic_negatives:
                with open(filepath, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for neg in synthetic_negatives:
                        writer.writerow([
                            neg["title_a"], 
                            neg["title_b"],
                            neg["score"],
                            "synthetic_negative",
                            0 # Label 0 for incorrect
                        ])
                logger.info(f"Added {len(synthetic_negatives)} synthetic hard negatives to dataset.")

        return filepath
        
    except Exception as e:
        logger.error(f"Failed to export feedback: {e}")
        return None
    finally:
        await db.close()

async def generate_match_mining_report():
    """
    Analysis of match quality over time.
    """
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT verdict, COUNT(*) as count 
            FROM feedback 
            GROUP BY verdict
        """)
        stats = await cursor.fetchall()
        return {row["verdict"]: row["count"] for row in stats}
    finally:
        await db.close()

async def generate_hard_negatives(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Generates synthetic 'incorrect' examples by finding markets that look similar 
    but are likely different (e.g., same event, different dates).
    """
    db = await get_db()
    try:
        # Get all unique titles
        cursor = await db.execute("SELECT DISTINCT title FROM markets")
        titles = [row["title"] for row in await cursor.fetchall()]
        
        if len(titles) < 10:
            return []
            
        negatives = []
        from backend.matcher import normalize_text, extract_keywords
        
        # Simple N^2 search for similar but distinct titles (limited for performance)
        for i in range(min(500, len(titles))):
            title_a = titles[i]
            kw_a = extract_keywords(title_a)
            if not kw_a: continue
            
            for j in range(i + 1, min(1000, len(titles))):
                title_b = titles[j]
                kw_b = extract_keywords(title_b)
                if not kw_b: continue
                
                intersection = kw_a & kw_b
                # If they share many keywords (3+) but are not identical
                if len(intersection) >= 3 and title_a != title_b:
                    negatives.append({
                        "title_a": title_a,
                        "title_b": title_b,
                        "score": len(intersection) / (len(kw_a | kw_b))
                    })
                    
                if len(negatives) >= limit:
                    break
            if len(negatives) >= limit:
                break
                
        return negatives
    except Exception as e:
        logger.error(f"Error generating negatives: {e}")
        return []
    finally:
        await db.close()

if __name__ == "__main__":
    # Quick CLI run
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(export_feedback_to_csv())
