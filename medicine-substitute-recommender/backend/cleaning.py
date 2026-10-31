import re

def clean_medicine_name(name: str) -> str:
    """Standardizes medicine name for matching."""
    if not isinstance(name, str):
        return ""
    name = name.lower().strip()
    return re.sub(r'\s+', ' ', name)

def parse_composition(comp_str: str):
    """
    Parses raw composition into list of tuples: [('salt', 'strength')]
    and canonical string key: 'salt1:strength1|salt2:strength2'
    """
    if not isinstance(comp_str, str) or not comp_str.strip():
        return [], ""
    
    parts = comp_str.split('+')
    parsed_salts = []
    
    for part in parts:
        part = part.strip().lower()
        match = re.search(r'^(.*?)\s*\(([\d\.]+\s*(?:mg|mcg|gm|g|ml|%|iu|w/v|w/w|v/v))\)$', part)
        if match:
            salt = match.group(1).strip()
            strength = match.group(2).replace(" ", "")
        else:
            match_fallback = re.search(r'^(.*?)\s*([\d\.]+\s*(?:mg|mcg|gm|g|ml|%|iu|w/v|w/w|v/v))$', part)
            if match_fallback:
                salt = match_fallback.group(1).strip()
                strength = match_fallback.group(2).replace(" ", "")
            else:
                salt = part.strip()
                strength = "unspecified"
        
        parsed_salts.append((salt, strength))
    
    parsed_salts.sort(key=lambda x: x[0])
    canonical_key = "|".join([f"{s}:{st}" for s, st in parsed_salts])
    return parsed_salts, canonical_key

def jaccard_similarity(set1: set, set2: set) -> float:
    """Calculates Jaccard similarity coefficient between two active ingredient sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0