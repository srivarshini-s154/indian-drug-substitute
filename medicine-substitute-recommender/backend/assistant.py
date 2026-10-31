
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)


class GroqAssistant:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()

        if not self.api_key:
            raise ValueError(
                f"GROQ_API_KEY is missing. Check: {ENV_PATH}"
            )

        self.model_name = os.getenv(
            "GROQ_MODEL",
            "qwen/qwen3.8-27b",
        ).strip()

        self.client = Groq(
            api_key=self.api_key,
            timeout=30.0,
            max_retries=1,
        )

        print("AI provider: Groq")
        print(f"AI model: {self.model_name}")
        print(f".env file found: {ENV_PATH.is_file()}")

    @staticmethod
    def _first_available(data: dict, *keys):
        """Return the first non-missing value."""
        for key in keys:
            value = data.get(key)

            if value is not None and value != "":
                return value

        return None

    @staticmethod
    def _clean_for_prompt(value):
        """Convert pandas/numpy values into JSON-friendly values."""
        if value is None:
            return None

        try:
            import pandas as pd

            if pd.isna(value):
                return None
        except (ImportError, TypeError, ValueError):
            pass

        if hasattr(value, "item"):
            try:
                return value.item()
            except (ValueError, TypeError):
                pass

        if isinstance(value, dict):
            return {
                str(k): GroqAssistant._clean_for_prompt(v)
                for k, v in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                GroqAssistant._clean_for_prompt(v)
                for v in value
            ]

        return value

    def _prepare_substitutes(self, substitutes: list) -> list:
        """
        Preserve backend ranking order.
        Never sort or rerank medicines inside the chatbot.
        """
        prepared = []

        for position, drug in enumerate(substitutes[:10], start=1):

            rank = self._first_available(drug, "rank")

            if rank is None:
                rank = position

            item = {
                "rank": rank,
                "name": drug.get("name"),
                "manufacturer": drug.get("manufacturer"),
                "composition": drug.get("composition"),
                "dosage_form": drug.get("dosage_form"),
                "price_inr": drug.get("price_inr"),
                "pack_size": drug.get("pack_size"),
                "price_per_unit": drug.get("price_per_unit"),
                "savings_pct": drug.get("savings_pct"),
                "side_effects": drug.get("side_effects"),

                # Side-effect similarity is a separate metric.
                "side_effect_similarity_pct": drug.get(
                    "side_effect_similarity_pct"
                ),

                "bayesian_rating": drug.get("bayesian_rating"),

                "composite_score": drug.get(
                    "composite_score",
                    drug.get("final_score"),
                ),
            }

            # Preserve all matching metrics independently.
            for field in (
                "profile_match",
                "profile_match_pct",
                "medicine_match",
                "medicine_match_pct",
                "composition_match",
                "composition_match_pct",
                "canonical_composition_key",
            ):
                if field in drug:
                    item[field] = drug[field]

            prepared.append(
                self._clean_for_prompt(item)
            )

        return prepared

    def explain_recommendations(
        self,
        query_drug: dict,
        substitutes: list,
        user_question: str,
    ) -> str:

        compact_substitutes = self._prepare_substitutes(
            substitutes
        )

        original_medicine = {
            "name": query_drug.get("name"),
            "manufacturer": query_drug.get("manufacturer"),
            "composition": query_drug.get("composition"),
            "dosage_form": query_drug.get("dosage_form"),
            "price_inr": query_drug.get("price_inr"),
            "pack_size": query_drug.get("pack_size"),
            "price_per_unit": query_drug.get("price_per_unit"),
            "side_effects": query_drug.get("side_effects"),
        }

        original_medicine = self._clean_for_prompt(
            original_medicine
        )

        database_context = {
            "searched_medicine": original_medicine,
            "substitutes_in_backend_order": compact_substitutes,
        }

        prompt = f"""
MEDICINE DATABASE CONTEXT:

{json.dumps(database_context, ensure_ascii=False, indent=2)}

USER QUESTION:
{user_question}


YOUR ROLE:
You are a medicine information and comparison assistant.
Answer the user's actual question using the supplied database context.


IMPORTANT METRIC MAPPING:

Always use the correct field for the metric being discussed.

1. Composition Match:
   Use composition_match_pct or composition_match.

2. Profile Match:
   Use profile_match_pct or profile_match.

3. Medicine Match:
   Use medicine_match_pct or medicine_match.

4. Side-Effect Similarity:
   Use side_effect_similarity_pct.

5. Price Savings:
   Use savings_pct.

NEVER confuse these metrics.

If the user asks why a medicine has a 100% profile match,
explain its profile match.

If the user asks why a medicine has a 100% composition match,
explain its composition match.

NEVER use side_effect_similarity_pct as a replacement
for composition_match_pct or profile_match_pct.

If the requested metric is unavailable, do not substitute
another metric. Briefly explain using the available information.


RANKING RULES:

1. Preserve the exact substitute order supplied by the backend.
2. Use the supplied rank field, or list position if unavailable.
3. Never independently reorder or rerank medicines.
4. Do not claim that ranking is based on Bayesian rating,
   savings, or profile match unless explicitly documented.
5. If the ranking formula is unavailable, say so briefly.


METRIC RULES:

1. Keep all metrics separate.
2. Use the exact numerical values supplied by the backend.
3. Never invent or recalculate scores.
4. A composition match does not automatically establish
   clinical interchangeability.
5. price_inr represents the entire pack price.
6. Mention pack sizes when comparing prices.
7. Use price_per_unit when appropriate.
8. Never interpret Bayesian rating as a percentage,
   probability, safety score, or effectiveness score
   unless its definition is explicitly supplied.
9. Never describe a percentage as savings unless it comes
   from savings_pct.


DATA ACCURACY:

1. Use the supplied database as the source of truth.
2. Never invent missing ingredients, prices, manufacturers,
   side effects, or numerical values.
3. Do not confuse the searched medicine with its substitutes.
4. Do not repeatedly announce missing database fields.
5. Mention missing information only when it is essential
   to answer the user's question accurately or safely.
6. Do not claim to have checked external sources.


MEDICAL SAFETY:

1. Never diagnose or prescribe.
2. Never provide individualized dosage instructions.
3. Never tell users to start, stop, or switch medicines.
4. Database scores and matching percentages do not
   guarantee clinical interchangeability.
5. Recommend consulting a qualified doctor or pharmacist
   before changing medication.
6. Prioritize medical attention for potentially serious symptoms.


RESPONSE STYLE:

1. Answer the exact question directly.
2. Give medium-sized responses, ideally 4-6 sentences.
3. Avoid both one-line answers and excessively long explanations.
4. Explain the most relevant metrics in simple language.
5. Keep each medicine's metrics together.
6. For ranking questions, mention the exact rank and medicine.
7. Explain what a matching percentage actually represents.
8. Do not list every metric unless the user asks for details.
9. Avoid repetitive disclaimers and unnecessary introductions.
10. Use friendly, natural language.
11. Use headings or bullet points only when they improve readability.
12. If the user greets you, respond briefly and naturally.
"""

        system_message = """
You are a careful, friendly medicine information assistant.

Your answers must be grounded in the supplied medicine database.

IMPORTANT:
Never confuse composition match, profile match,
medicine match, and side-effect similarity.

Use the correct database field:

- Composition match: composition_match_pct
- Profile match: profile_match_pct
- Medicine match: medicine_match_pct
- Side-effect similarity: side_effect_similarity_pct
- Price savings: savings_pct

When a user asks about profile match, explain profile match.
When a user asks about composition match, explain composition match.

NEVER describe a side-effect similarity score as a
composition or profile match.

Preserve the backend's ranking order.
Never invent metric definitions, values, or medical information.

Keep answers medium-sized, ideally 4-6 sentences.
Explain the most relevant information without listing
every database field.

Do not repeatedly mention missing database information.
Mention limitations only when relevant to the question
or necessary for accuracy and medical safety.

Never diagnose, prescribe, or recommend personal
medication changes.

Database similarity does not guarantee clinical
interchangeability. Recommend consulting a doctor
or pharmacist before switching medicines.

Use simple, natural, conversational language.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_message.strip(),
                    },
                    {
                        "role": "user",
                        "content": prompt.strip(),
                    },
                ],
                temperature=0.1,
                max_tokens=450,
            )

            content = response.choices[0].message.content

            if content and content.strip():
                return content.strip()

            return (
                "I couldn't generate an answer just now. "
                "Please try asking in a different way."
            )

        except Exception as err:
            print(
                f"Groq request failed: {type(err).__name__}"
            )

            return (
                "Sorry, I couldn't generate an answer right now. "
                "Please try again in a moment."
            )
