
import os
import re
from typing import Any

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.recommender import SubstituteRecommender
from backend.stats_analysis import StatsEngine
from backend.assistant import GroqAssistant


app = FastAPI(
    title="Indian Medicine Substitute Recommender API",
    version="1.0",
)


# Enable CORS for frontend fetches.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize core services.
recommender = SubstituteRecommender()
stats_engine = StatsEngine()
assistant = GroqAssistant()


# Normalize only known wording variations.
# Add aliases only after verifying that the terms are equivalent.
SIDE_EFFECT_ALIASES = {
    "head pain": "headache",
    "giddiness": "dizziness",
    "feeling sick": "nausea",
    "throwing up": "vomiting",
}


def normalize_side_effects(value: Any) -> list[str] | None:
    """
    Normalize a clearly delimited list of side-effect terms.

    Supports lists and strings separated by semicolons,
    newlines, or vertical bars.

    Returns None when information is missing or unusable.
    Comma-separated prose is not split automatically because
    commas may occur inside longer medical descriptions.
    """
    if value is None:
        return None

    if isinstance(value, list):
        raw_items = value

    elif isinstance(value, str):
        text = value.strip()

        if not text or text.lower() in {
            "nan",
            "none",
            "null",
            "n/a",
            "not available",
            "unknown",
            "not available in the dataset",
        }:
            return None

        raw_items = re.split(r"[;\n|]", text)

    else:
        return None

    effects: list[str] = []

    for item in raw_items:
        term = str(item).strip().lower()

        # Remove leading bullets and normalize whitespace.
        term = re.sub(r"^[\s•\-]+", "", term)
        term = re.sub(r"\s+", " ", term)
        term = term.rstrip(" .")

        if not term or term in {
            "nan",
            "none",
            "null",
            "n/a",
        }:
            continue

        # Normalize verified wording variants.
        term = SIDE_EFFECT_ALIASES.get(term, term)

        if term not in effects:
            effects.append(term)

    return effects or None


def compare_side_effects(
    original_value: Any,
    substitute_value: Any,
) -> dict:
    """
    Compare recorded side-effect terms.

    This function compares dataset entries only. It does not
    determine clinical equivalence or which medicine is safer.
    """
    original = normalize_side_effects(original_value)
    substitute = normalize_side_effects(substitute_value)

    # Do not claim there are no additional effects if either
    # medicine has missing or unusable information.
    if original is None or substitute is None:
        return {
            "status": "insufficient_data",
            "shared_effects": [],
            "substitute_only_in_data": [],
            "original_only_in_data": [],
            "message": (
                "A reliable comparison cannot be made because "
                "side-effect information is missing or not "
                "recorded in a comparable format."
            ),
        }

    original_set = set(original)
    substitute_set = set(substitute)

    shared_effects = sorted(
        original_set.intersection(substitute_set)
    )

    substitute_only = sorted(
        substitute_set.difference(original_set)
    )

    original_only = sorted(
        original_set.difference(substitute_set)
    )

    return {
        "status": "compared",
        "shared_effects": shared_effects,
        "substitute_only_in_data": substitute_only,
        "original_only_in_data": original_only,
        "message": (
            "Differences reflect the available dataset only. "
            "They do not establish that an effect is exclusive "
            "to either medicine or that either medicine is safer."
        ),
    }


# Pydantic schema for chatbot requests.
class ChatRequest(BaseModel):
    question: str
    query_drug: dict
    substitutes: list


@app.get("/api/search")
def autocomplete_search(
    q: str = Query(..., min_length=2),
):
    """Return matching medicine names for autocomplete."""
    q_clean = q.lower().strip()

    matches = recommender.df[
        recommender.df["clean_name"].str.contains(
            q_clean,
            regex=False,
            na=False,
        )
    ]["name"].head(15).tolist()

    return {
        "query": q,
        "results": matches,
    }


@app.get("/api/recommend")
def get_recommendations(
    name: str = Query(...),
    top: int = Query(10, ge=1, le=20),
):
    """
    Return ranked substitutes and a structured side-effect
    comparison for each substitute.
    """
    res = recommender.find_substitutes(
        query_name=name,
        top_n=top,
    )

    if "error" in res:
        raise HTTPException(
            status_code=404,
            detail=res["error"],
        )

    if not isinstance(res, dict):
        raise HTTPException(
            status_code=500,
            detail=(
                "The recommender returned an unexpected "
                "response format."
            ),
        )

    query_drug = res.get("query_drug") or {}
    substitutes = res.get("substitutes") or []

    if (
        not isinstance(query_drug, dict)
        or not isinstance(substitutes, list)
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "The recommender response is missing "
                "expected medicine data."
            ),
        )

    enriched_substitutes = []

    for item in substitutes:
        if not isinstance(item, dict):
            enriched_substitutes.append(item)
            continue

        # Copy each substitute instead of mutating the original.
        sub = dict(item)

        sub["side_effect_comparison"] = compare_side_effects(
            query_drug.get("side_effects"),
            sub.get("side_effects"),
        )

        enriched_substitutes.append(sub)

    return {
        **res,
        "query_drug": query_drug,
        "substitutes": enriched_substitutes,
    }


@app.get("/api/stats")
def get_statistical_summaries():
    """
    Return price summaries, Kruskal-Wallis results,
    and savings confidence intervals.
    """
    return {
        "price_summaries": stats_engine.get_price_summaries(),
        "kruskal_wallis": stats_engine.run_kruskal_wallis(),
        "savings_ci": (
            stats_engine.get_savings_confidence_interval()
        ),
    }


@app.post("/api/chat")
def chat_explanation(req: ChatRequest):
    """Send the current medicine data and question to Groq."""
    explanation = assistant.explain_recommendations(
        query_drug=req.query_drug,
        substitutes=req.substitutes,
        user_question=req.question,
    )

    return {
        "explanation": explanation,
    }


# Serve the compiled frontend when frontend/dist exists.
frontend_dist_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "frontend",
    "dist",
)

if os.path.exists(frontend_dist_path):
    app.mount(
        "/",
        StaticFiles(
            directory=frontend_dist_path,
            html=True,
        ),
        name="frontend",
    )

else:

    @app.get("/")
    def root_status():
        return JSONResponse({
            "status": "online",
            "message": (
                "MediSubstitute AI Backend API is running."
            ),
            "frontend_dev_url": "http://localhost:5173",
            "swagger_docs": "http://127.0.0.1:8000/docs",
        })
