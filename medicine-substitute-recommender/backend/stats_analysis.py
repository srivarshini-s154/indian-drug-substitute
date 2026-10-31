import pandas as pd
import numpy as np
from scipy import stats
from backend.config import PROCESSED_DATA_PATH

class StatsEngine:
    def __init__(self, data_path=PROCESSED_DATA_PATH):
        self.df = pd.read_csv(data_path)

    def get_price_summaries(self):
        """Returns price distribution metrics by primary dosage form."""
        top_forms = self.df['dosage_form'].value_counts().head(5).index
        filtered = self.df[self.df['dosage_form'].isin(top_forms)]
        
        summary = filtered.groupby('dosage_form')['price_inr'].agg(
            count='count',
            mean='mean',
            std='std',
            median='median',
            q25=lambda x: x.quantile(0.25),
            q75=lambda x: x.quantile(0.75)
        ).reset_index()
        
        summary['iqr'] = summary['q75'] - summary['q25']
        return summary.round(2).to_dict(orient='records')

    def run_kruskal_wallis(self, min_products_per_mfg=2):
        """Runs Kruskal-Wallis test across manufacturers with multiple products."""
        top_comp = self.df['canonical_composition_key'].value_counts().index[0]
        comp_data = self.df[self.df['canonical_composition_key'] == top_comp]
        
        # Filter manufacturers with at least min_products_per_mfg
        mfg_counts = comp_data['manufacturer_name'].value_counts()
        valid_mfgs = mfg_counts[mfg_counts >= min_products_per_mfg].index
        
        filtered_data = comp_data[comp_data['manufacturer_name'].isin(valid_mfgs)]
        groups = [grp['price_inr'].values for _, grp in filtered_data.groupby('manufacturer_name')]
        
        if len(groups) < 2:
            return {"composition": top_comp, "error": "Insufficient groups for test"}
            
        h_stat, p_val = stats.kruskal(*groups)
        return {
            "composition": top_comp,
            "sample_size": int(len(filtered_data)),
            "manufacturer_count": int(len(groups)),
            "h_statistic": round(float(h_stat), 4),
            "p_value": float(p_val),
            "statistically_significant": bool(p_val < 0.05)
        }

    def get_savings_confidence_interval(self):
        """Calculates 95% CI for percentage savings."""
        min_prices = self.df.groupby('canonical_composition_key')['price_inr'].transform('min')
        savings = ((self.df['price_inr'] - min_prices) / self.df['price_inr']) * 100
        valid_savings = savings[savings > 0]
        
        mean_val = float(valid_savings.mean())
        sem_val = float(stats.sem(valid_savings))
        ci = stats.t.interval(0.95, len(valid_savings)-1, loc=mean_val, scale=sem_val)
        
        return {
            "mean_savings_pct": round(mean_val, 2),
            "median_savings_pct": round(float(valid_savings.median()), 2),
            "ci_95_lower": round(float(ci[0]), 2),
            "ci_95_upper": round(float(ci[1]), 2)
        }