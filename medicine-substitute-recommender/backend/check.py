import json
from backend.recommender import SubstituteRecommender
from pathlib import Path



def show_fields(label, drug):
    print(f"\n{'=' * 65}")
    print(label)
    print("=" * 65)

    if not isinstance(drug, dict):
        print("ERROR: Expected a dictionary.")
        print("Received:", repr(drug))
        return

    fields = [
        "name",
        "manufacturer",
        "composition",
        "raw_composition",
        "dosage_form",
        "price_inr",
        "pack_size",
        "price_per_unit",
        "savings_pct",
        "side_effects",
        "side_effect_similarity_pct",
        "bayesian_rating",
    ]

    for field in fields:
        value = drug.get(field)
        status = "OK" if value is not None else "MISSING"
        print(f"{field:30} [{status}] {value}")


def main():
    print("\nMEDICINE RECOMMENDER → LLM DATA CHECK")

    recommender = SubstituteRecommender()

    # Use the same medicine name you searched on the website.
    medicine_name = "Crocin Pain Relief Tablet"

    # Adjust the method name if your recommender uses another name.
    result = recommender.find_substitutes(medicine_name)

    if not isinstance(result, dict):
        print("Unexpected recommender response:", result)
        return

    print("\nResponse keys:", list(result.keys()))

    if "error" in result or "message" in result:
        print("Recommender response:", result)
        return

    query_drug = result.get("query_drug", {})
    substitutes = result.get("substitutes", [])

    show_fields("ORIGINAL MEDICINE", query_drug)

    print(f"\nTotal substitutes returned: {len(substitutes)}")

    algina = next(
        (
            drug for drug in substitutes
            if "Algina Plus 50mg/650mg Tablet" in str(drug.get("name", "")).lower()
        ),
        None,
    )

    if algina:
        show_fields("ALGINA PLUS — SUBSTITUTE", algina)
    else:
        print("\nAlgina Plus was not found in the returned substitutes.")

        if substitutes:
            show_fields("FIRST RETURNED SUBSTITUTE", substitutes[0])

    print("\n" + "=" * 65)
    print("LLM DATA AVAILABILITY CHECK")
    print("=" * 65)

    for drug in substitutes[:10]:
        name = drug.get("name", "Unknown")
        composition = drug.get("composition")
        dosage_form = drug.get("dosage_form")

        print(
            f"{name}\n"
            f"  composition: {composition!r}\n"
            f"  dosage_form: {dosage_form!r}"
        )


if __name__ == "__main__":
    main()
