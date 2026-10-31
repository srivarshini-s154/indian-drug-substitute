
import re
from typing import Any


# These aliases help match common wording variations.
# Expand this dictionary based on the terms in your dataset.
ALIASES = {
    "head pain": "headache",
    "feeling sick": "nausea",
    "vomiting": "vomiting",
    "throwing up": "vomiting",
    "dizziness": "dizziness",
    "giddiness": "dizziness",
    "stomach pain": "abdominal pain",
    "abdominal pain": "abdominal pain",
}


def normalize_side_effects(value: Any) -> list[str] | None:
    """
    Convert a structured list or clearly delimited string into
    normalized terms.

    Return None when the information is missing or unusable.
    """
    if value is None:
        return None

    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        text = value.strip()

        if not text or text.lower() in {
            "nan", "none", "null", "n/a", "not available",
            "unknown", "not available in the dataset"
        }:
            return None

        # Only split on clear delimiters. Do not split on commas
        # inside sentences if the dataset contains full descriptions.
        raw_items = re.split(r"[;\n|]", text)
    else:
        return None

    effects = []

    for item in raw_items:
        term = str(item).strip().lower()
        term = re.sub(r"^[\s•\-]+", "", term)
        term = re.sub(r"\s+", " ", term)
        term = term.rstrip(" .")

        if not term or term in {"nan", "none", "null", "n/a"}:
            continue

        term = ALIASES.get(term, term)

        if term not in effects:
            effects.append(term)

    return effects or None


def compare_side_effects(
    original_value: Any,
    substitute_value: Any,
) -> dict:
    """
    Compare recorded side-effect terms. This is a dataset comparison,
    not a clinical assessment of which medicine is safer.
    """
    original = normalize_side_effects(original_value)
    substitute = normalize_side_effects(substitute_value)

    if original is None or substitute is None:
        return {
            "status": "insufficient_data",
            "shared_effects": [],
            "substitute_only_in_data": [],
            "original_only_in_data": [],
            "message": (
                "A reliable comparison cannot be made because side-effect "
                "information is missing or not recorded in a comparable format."
            ),
        }

    original_set = set(original)
    substitute_set = set(substitute)

    return {
        "status": "compared",
        "shared_effects": sorted(original_set & substitute_set),
        "substitute_only_in_data": sorted(substitute_set - original_set),
        "original_only_in_data": sorted(original_set - substitute_set),
        "message": (
            "Differences reflect the available dataset only. They do not "
            "establish that an effect is exclusive to either medicine."
        ),
    }
