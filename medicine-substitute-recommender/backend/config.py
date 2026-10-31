import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_PATH = DATA_DIR / "processed" / "medicines_clean.csv"

# Recommender Weights for TOPSIS / Multi-Criteria Decision Analysis
# Weights must sum to 1.0
WEIGHT_PRICE = 0.30      # Higher weight on savings
WEIGHT_SIDE_EFFECTS = 0.30 # Similarity in side-effect profiles
WEIGHT_RELIABILITY = 0.40 # Bayesian weighted user rating

# Minimum Jaccard threshold for candidate salt matches (1.0 = exact salt & strength match)
SALT_MATCH_THRESHOLD = 1.0

# Groq API Configuration
GROQ_MODEL = "qwen/qwen3.8-27b"