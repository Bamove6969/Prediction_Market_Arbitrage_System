"""
Semantic Matching Script - Identifies identically-worded questions across platforms
Uses natural language understanding to match questions with different wording but same meaning
"""
import asyncio
import logging
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class SemanticQuestionMatcher:
    """
    Advanced semantic matching for prediction market questions
    Identifies questions that are semantically identical despite different wording
    """
    
    def __init__(self):
        # Common normalization patterns
        self.date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),?\s+\d{4}\b',
        ]
        
        self.number_pattern = r'\b\d+(?:\.\d+)?%?\b'
        
        # Entities to preserve during normalization
        self.preserved_entities = []
        
    def normalize_question(self, question: str) -> str:
        """
        Normalize a question for comparison
        - Remove extra whitespace
        - Standardize dates
        - Standardize numbers
        - Remove platform-specific formatting
        """
        # Convert to lowercase
        normalized = question.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common filler phrases
        fillers = [
            'will ', 'does ', 'do ', 'is ', 'are ', 'was ', 'were ',
            'what ', 'when ', 'where ', 'who ', 'why ', 'how ',
            'the ', 'a ', 'an ', 'of ', 'in ', 'on ', 'at ', 'to ', 'for ',
            'by ', 'with ', 'from ', 'as ', 'that ', 'this ',
        ]
        
        # Remove question marks and other punctuation
        normalized = re.sub(r'[?!,.\']', '', normalized)
        
        # Extract and preserve key numbers (except years)
        numbers = []
        for num in re.findall(self.number_pattern, normalized):
            if num not in ['2024', '2025', '2026', '2027']:
                numbers.append(num)
        
        # Extract key entities (capitalized words, proper nouns)
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question)
        
        # Remove stopwords but keep key terms
        stopwords = set([
            'will', 'whether', 'if', 'that', 'this', 'which', 'what',
            'more', 'than', 'less', 'at', 'least', 'most', 'exactly',
            'over', 'under', 'above', 'below', 'between', 'during',
            'before', 'after', 'by', 'from', 'to', 'in', 'on', 'at',
        ])
        
        words = normalized.split()
        key_words = [w for w in words if w not in stopwords and len(w) > 2]
        
        return {
            'normalized': ' '.join(key_words),
            'numbers': set(numbers),
            'entities': set(entities),
            'original': question
        }
    
    def extract_semantic_signature(self, question: str) -> Dict[str, Any]:
        """
        Extract a semantic signature for comparison
        """
        normalized = self.normalize_question(question)
        
        # Identify the core event/outcome
        core_event = normalized['normalized']
        
        # Identify constraints (numbers, dates, conditions)
        constraints = {
            'numbers': normalized['numbers'],
            'entities': normalized['entities']
        }
        
        return {
            'core_event': core_event,
            'constraints': constraints,
            'full_normalized': normalized
        }
    
    def calculate_semantic_similarity(self, sig1: Dict, sig2: Dict) -> Tuple[float, List[str]]:
        """
        Calculate semantic similarity between two question signatures
        Returns similarity score (0-1) and list of differences
        """
        differences = []
        similarity_score = 0.0
        
        # 1. Core event similarity (word overlap)
        words1 = set(sig1['core_event'].split())
        words2 = set(sig2['core_event'].split())
        
        if words1 and words2:
            jaccard = len(words1 & words2) / len(words1 | words2)
            similarity_score += jaccard * 0.5
        else:
            differences.append("No core event words to compare")
        
        # 2. Number constraint matching
        nums1 = sig1['constraints']['numbers']
        nums2 = sig2['constraints']['numbers']
        
        if nums1 and nums2:
            if nums1 == nums2:
                similarity_score += 0.3
            elif nums1 & nums2:  # Partial overlap
                similarity_score += 0.15
            else:
                differences.append(f"Different numbers: {nums1} vs {nums2}")
        elif not nums1 and not nums2:
            similarity_score += 0.3  # Both have no numbers
        else:
            differences.append(f"One has numbers, other doesn't: {nums1} vs {nums2}")
        
        # 3. Entity matching
        entities1 = sig1['constraints']['entities']
        entities2 = sig2['constraints']['entities']
        
        if entities1 and entities2:
            entity_overlap = len(entities1 & entities2)
            entity_union = len(entities1 | entities2)
            if entity_union > 0:
                entity_sim = entity_overlap / entity_union
                similarity_score += entity_sim * 0.2
        elif not entities1 and not entities2:
            similarity_score += 0.2
        else:
            differences.append(f"Entity mismatch: {entities1} vs {entities2}")
        
        return min(1.0, similarity_score), differences
    
    def is_semantic_match(self, question1: str, question2: str, threshold: float = 0.75) -> Tuple[bool, Dict[str, Any]]:
        """
        Determine if two questions are semantically identical
        """
        sig1 = self.extract_semantic_signature(question1)
        sig2 = self.extract_semantic_signature(question2)
        
        similarity, differences = self.calculate_semantic_similarity(sig1, sig2)
        
        is_match = similarity >= threshold
        
        result = {
            'is_match': is_match,
            'similarity_score': similarity,
            'threshold': threshold,
            'differences': differences,
            'question1_sig': sig1['core_event'],
            'question2_sig': sig2['core_event']
        }
        
        return is_match, result
    
    def batch_match(self, pairs: List[Dict[str, Any]], threshold: float = 0.75) -> List[Dict[str, Any]]:
        """
        Process multiple pairs and return only semantic matches
        """
        matches = []
        
        for pair in pairs:
            question_a = pair['marketA']['title']
            question_b = pair['marketB']['title']
            
            is_match, analysis = self.is_semantic_match(question_a, question_b, threshold)
            
            if is_match:
                matches.append({
                    'marketA': pair['marketA'],
                    'marketB': pair['marketB'],
                    'semantic_analysis': analysis,
                    'original_roi': pair.get('roi', 0),
                    'match_score': pair.get('matchScore', 0)
                })
        
        logger.info(f"Semantic matching: {len(matches)}/{len(pairs)} pairs matched")
        return matches


async def run_semantic_matching(pairs: List[Dict[str, Any]], threshold: float = 0.75) -> List[Dict[str, Any]]:
    """
    Main entry point for semantic matching
    """
    matcher = SemanticQuestionMatcher()
    
    # Run in executor to avoid blocking
    loop = asyncio.get_event_loop()
    matches = await loop.run_in_executor(
        None,
        matcher.batch_match,
        pairs,
        threshold
    )
    
    return matches


if __name__ == "__main__":
    # Test example
    test_pairs = [
        {
            "marketA": {
                "title": "Will the Fed raise interest rates by more than 0.25% in March 2025?",
                "platform": "PredictIt",
                "yesPrice": 0.45,
                "url": "https://predictit.org/market/123"
            },
            "marketB": {
                "title": "Federal Reserve interest rate increase exceeding 25 basis points in March 2025",
                "platform": "Polymarket",
                "yesPrice": 0.42,
                "url": "https://polymarket.com/event/456"
            },
            "roi": 13.5
        }
    ]
    
    matcher = SemanticQuestionMatcher()
    result = matcher.batch_match(test_pairs)
    
    print(f"Matches found: {len(result)}")
    if result:
        print(f"Analysis: {result[0]['semantic_analysis']}")
