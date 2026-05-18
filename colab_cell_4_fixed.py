# 4. ADVANCED EXTRACTION & COMPARISON LOGIC

def extract_dates(text: str) -> Set[Tuple[int, int, int]]:
    """
    Extract all dates from text and return as set of (year, month, day) tuples.
    Handles: "March 31", "March 2027", "3/31/2026", "by March 31st", etc.
    """
    dates = set()
    
    # Common patterns
    patterns = [
        r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',  # 3/31/2026
        r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b',  # 2026-03-31
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b',
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                parsed = dateparser.parse(match.group(0), settings={'PREFER_DATES_FROM': 'future'})
                if parsed:
                    dates.add((parsed.year, parsed.month, parsed.day))
            except:
                pass
    
    return dates

def extract_numbers(text: str) -> Set[float]:
    """
    Extract all meaningful numbers (excluding years).
    Handles: "4.5%", "4.2-4.3%", "$100", "5.5 percent", etc.
    """
    numbers = set()
    
    # Find all numbers including decimals and ranges
    for match in re.finditer(r'\d+(?:\.\d+)?', text):
        num = float(match.group())
        # Exclude years (2020-2030 range)
        if not (2020 <= num <= 2030):
            numbers.add(num)
    
    return numbers

def extract_entities(text: str) -> Set[str]:
    """
    Extract named entities (people, organizations, locations).
    Example: "Trump" vs "Biden", "Federal Reserve" vs "ECB"
    """
    doc = nlp(text)
    entities = set()
    
    for ent in doc.ents:
        if ent.label_ in ['PERSON', 'ORG', 'GPE', 'NORP']:  # Person, Org, Geo-Political Entity, Nationalities
            entities.add(ent.text.lower())
    
    return entities

def extract_temporal_modifiers(text: str) -> Set[str]:
    """
    Extract temporal context: "by", "before", "after", "during", "in", "on"
    "by March 31" ≠ "after March 31"
    """
    modifiers = set()
    temporal_words = ['by', 'before', 'after', 'during', 'in', 'on', 'until', 'through', 'within']
    
    text_lower = text.lower()
    for word in temporal_words:
        if re.search(rf'\b{word}\b', text_lower):
            modifiers.add(word)
    
    return modifiers

def are_questions_compatible(title_a: str, title_b: str) -> Tuple[bool, str]:
    """
    Deep compatibility check. Returns (is_compatible, reason).
    """
    dates_a = extract_dates(title_a)
    dates_b = extract_dates(title_b)
    
    # CRITICAL: If both have dates and they don't overlap, REJECT
    if dates_a and dates_b:
        if dates_a.isdisjoint(dates_b):
            return False, f"Date mismatch: {dates_a} vs {dates_b}"
    
    # Check temporal modifiers
    temp_a = extract_temporal_modifiers(title_a)
    temp_b = extract_temporal_modifiers(title_b)
    
    # If one says "by" and other says "after", they're opposite
    if ('by' in temp_a or 'before' in temp_a) and ('after' in temp_b):
        return False, "Temporal conflict: 'by/before' vs 'after'"
    if ('by' in temp_b or 'before' in temp_b) and ('after' in temp_a):
        return False, "Temporal conflict: 'by/before' vs 'after'"
    
    # Extract numbers
    nums_a = extract_numbers(title_a)
    nums_b = extract_numbers(title_b)
    
    # CRITICAL: If both have numbers and they're completely different, REJECT
    if nums_a and nums_b:
        # FIXED: Use different tolerance for small vs large numbers
        compatible = False
        for na in nums_a:
            for nb in nums_b:
                # Small numbers (< 10, like percentages): absolute tolerance
                if na < 10 and nb < 10:
                    if abs(na - nb) < 0.15:  # 4.5 vs 4.4 OK
                        compatible = True
                        break
                # Large numbers (>= 10, like scores): strict tolerance
                else:
                    if abs(na - nb) < 1.0:  # 70 vs 71 OK, 70 vs 80 NOT OK
                        compatible = True
                        break
            if compatible:
                break
        
        if not compatible:
            return False, f"Number mismatch: {nums_a} vs {nums_b}"
    
    # Check entities (people, orgs)
    entities_a = extract_entities(title_a)
    entities_b = extract_entities(title_b)
    
    # If both mention entities and they're completely different, likely different questions
    if entities_a and entities_b:
        if entities_a.isdisjoint(entities_b):
            # Check if they're related (e.g., "Trump" and "Donald Trump")
            related = False
            for ea in entities_a:
                for eb in entities_b:
                    if ea in eb or eb in ea:
                        related = True
                        break
                if related:
                    break
            
            if not related:
                return False, f"Entity mismatch: {entities_a} vs {entities_b}"
    
    return True, "Compatible"

print("✅ Advanced extraction logic loaded!")
