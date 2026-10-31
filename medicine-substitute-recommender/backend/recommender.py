import re
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.config import PROCESSED_DATA_PATH, WEIGHT_PRICE, WEIGHT_SIDE_EFFECTS, WEIGHT_RELIABILITY
from backend.cleaning import clean_medicine_name, parse_composition, jaccard_similarity

def extract_pack_quantity(pack_label: str) -> int:
    """Extracts numeric unit count from pack label (e.g., 'strip of 10 tablets' -> 10)."""
    if not isinstance(pack_label, str):
        return 1
    match = re.search(r'(\d+)', pack_label)
    if match:
        val = int(match.group(1))
        return val if val > 0 else 1
    return 1

class SubstituteRecommender:
    def __init__(self, data_path=PROCESSED_DATA_PATH):
        self.df = pd.read_csv(data_path)
        self.df['side_effects_text'] = self.df['side_effects_text'].fillna("No side effect details available.")
        self.df['pack_size_label'] = self.df['pack_size_label'].fillna("Standard Pack")
        
        # Precompute TF-IDF matrix for side effects
        self.tfidf = TfidfVectorizer(stop_words='english')
        self.tfidf_matrix = self.tfidf.fit_transform(self.df['side_effects_text'])

    def find_substitutes(self, query_name: str, top_n: int = 10):
        clean_q = clean_medicine_name(query_name)
        
        match = self.df[self.df['clean_name'] == clean_q]
        if match.empty:
            match = self.df[self.df['clean_name'].str.contains(clean_q, regex=False, na=False)]
            if match.empty:
                return {"error": f"Medicine '{query_name}' not found in database."}
        
        target_drug = match.iloc[0]
        target_form = target_drug['dosage_form']
        target_price = float(target_drug['price_inr'])
        target_idx = target_drug.name
        
        target_pack_qty = extract_pack_quantity(target_drug['pack_size_label'])
        target_unit_price = round(target_price / target_pack_qty, 2)
        
        target_salts_list, _ = parse_composition(target_drug['raw_composition'])
        target_salts_set = set(target_salts_list)
        
        candidates = self.df[
            (self.df['dosage_form'] == target_form) & 
            (self.df.index != target_idx)
        ].copy()
        
        def calculate_jaccard(raw_comp):
            salts_list, _ = parse_composition(raw_comp)
            return jaccard_similarity(target_salts_set, set(salts_list))

        candidates['jaccard_score'] = candidates['raw_composition'].apply(calculate_jaccard)
        candidates = candidates[candidates['jaccard_score'] == 1.0].copy()
        
        if candidates.empty:
            return {"message": "No exact composition substitutes found for this medicine format.", "target": target_drug.to_dict()}
        
        # Scoring Metrics
        candidates['price_savings_pct'] = ((target_price - candidates['price_inr']) / target_price) * 100
        min_p, max_p = candidates['price_inr'].min(), candidates['price_inr'].max()
        candidates['price_score'] = (max_p - candidates['price_inr']) / (max_p - min_p) if max_p > min_p else 1.0

        candidate_indices = candidates.index.tolist()
        target_tfidf = self.tfidf_matrix[target_idx]
        candidate_tfidf = self.tfidf_matrix[candidate_indices]
        candidates['side_effect_score'] = cosine_similarity(target_tfidf, candidate_tfidf).flatten()

        min_r, max_r = candidates['bayesian_rating'].min(), candidates['bayesian_rating'].max()
        candidates['reliability_score'] = (candidates['bayesian_rating'] - min_r) / (max_r - min_r) if max_r > min_r else 1.0

        candidates['final_score'] = (
            WEIGHT_PRICE * candidates['price_score'] +
            WEIGHT_SIDE_EFFECTS * candidates['side_effect_score'] +
            WEIGHT_RELIABILITY * candidates['reliability_score']
        )
        
        ranked_candidates = candidates.sort_values(by='final_score', ascending=False).head(top_n)
        
        results = []
        for rank, (_, row) in enumerate(ranked_candidates.iterrows(), 1):
            sub_price = float(row['price_inr'])
            sub_pack_qty = extract_pack_quantity(row['pack_size_label'])
            sub_unit_price = round(sub_price / sub_pack_qty, 2)

            results.append({
                "rank": rank,
                "name": row['name'],
                "manufacturer": row['manufacturer_name'],
                "price_inr": round(sub_price, 2),
                "pack_size": row['pack_size_label'],
                "price_per_unit": sub_unit_price,
                "savings_pct": round(float(row['price_savings_pct']), 1),
                "side_effects": row['side_effects_text'],
                "side_effect_similarity_pct": round(float(row['side_effect_score'] * 100), 1),
                "bayesian_rating": round(float(row['bayesian_rating']), 1),
                "composite_score": round(float(row['final_score']), 3)
            })

        return {
            "query_drug": {
                "name": target_drug['name'],
                "manufacturer": target_drug['manufacturer_name'],
                "price_inr": round(target_price, 2),
                "pack_size": target_drug['pack_size_label'],
                "price_per_unit": target_unit_price,
                "composition": target_drug['raw_composition'],
                "dosage_form": target_form,
                "side_effects": target_drug['side_effects_text']
            },
            "substitutes": results
        }