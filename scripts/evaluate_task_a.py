"""
Task A Evaluation
=================
Measures review generation quality against real Yelp reviews.

Metrics:
- ROUGE-1, ROUGE-2, ROUGE-L  : n-gram overlap with real reviews
- BERTScore                   : semantic similarity
- Rating RMSE                 : predicted vs actual star rating
- Rating MAE                  : mean absolute error on ratings

Usage:
    python -m scripts.evaluate_task_a --samples 50
"""

import asyncio
import argparse
import json
import math
import random
import httpx
from rouge_score import rouge_scorer
from bert_score import score as bert_score


API_URL = "http://localhost:8000/api/v1/task-a/generate"
PROFILES_PATH = "data/processed/user_profiles.json"
REVIEWS_PATH = "data/raw/yelp_academic_dataset_review.json"
BUSINESSES_PATH = "data/raw/yelp_academic_dataset_business.json"




def load_evaluation_pairs(
    profiles_path: str,
    reviews_path: str,
    businesses_path: str,
    n_samples: int = 50,
    min_reviews: int = 10
) -> list[dict]:
    """
    Build evaluation pairs: (user_profile, item, ground_truth_review, ground_truth_stars)

    Strategy:
    - Pick users with >= min_reviews (enough history to build a profile)
    - For each user, find one review NOT in their profile history (held-out)
    - Use that item as the test item and that review as ground truth
    """
    print("Loading profiles...")
    with open(profiles_path) as f:
        profiles = json.load(f)

    print("Loading businesses...")
    businesses = {}
    with open(businesses_path) as f:
        for line in f:
            biz = json.loads(line)
            businesses[biz["business_id"]] = biz

    print("Loading reviews...")
    reviews_by_user: dict[str, list] = {}
    with open(reviews_path) as f:
        for line in f:
            r = json.loads(line)
            uid = r.get("user_id")
            if uid in profiles:
                reviews_by_user.setdefault(uid, []).append(r)

    print("Building evaluation pairs...")
    pairs = []
    eligible_users = [
        uid for uid, p in profiles.items()
        if p["total_reviews"] >= min_reviews
    ]
    random.shuffle(eligible_users)

    for uid in eligible_users:
        if len(pairs) >= n_samples:
            break

        profile = profiles[uid]
        all_reviews = reviews_by_user.get(uid, [])

        # items already in profile history
        history_ids = {r["item_id"] for r in profile["review_history"]}

        # find a held-out review not in history
        held_out = [
            r for r in all_reviews
            if r.get("business_id") not in history_ids
            and r.get("text", "").strip()
            and len(r.get("text", "").split()) > 20
        ]

        if not held_out:
            continue

        # pick the most recent held-out review
        held_out = sorted(held_out, key=lambda r: r.get("date", ""), reverse=True)
        test_review = held_out[0]
        biz_id = test_review.get("business_id", "")
        biz = businesses.get(biz_id, {})

        if not biz:
            continue

        cats = biz.get("categories") or []
        if isinstance(cats, str):
            cats = [c.strip() for c in cats.split(",")]

        pairs.append({
            "user_id": uid,
            "user_profile": profile,
            "item": {
                "item_id": biz_id,
                "name": biz.get("name", "Unknown"),
                "category": cats[0] if cats else "General",
                "subcategories": cats[1:4],
                "avg_community_rating": biz.get("stars"),
                "description": None,
                "price_range": biz.get("attributes", {}).get("RestaurantsPriceRange2"),
                "attributes": {}
            },
            "ground_truth_review": test_review["text"],
            "ground_truth_stars": float(test_review["stars"])
        })

    print(f"Built {len(pairs)} evaluation pairs.")
    return pairs


async def call_task_a(client: httpx.AsyncClient, pair: dict) -> dict | None:
    """Call the Task A endpoint for one evaluation pair."""
    payload = {
        "user_id": pair["user_id"],
        "item": pair["item"],
        "nigerian_mode": False
    }
    try:
        response = await client.post(API_URL, json=payload, timeout=60.0)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error for user {pair['user_id']}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Request failed for user {pair['user_id']}: {e}")
        return None
    


def compute_rouge(predictions: list[str], references: list[str]) -> dict:
    """Compute ROUGE-1, ROUGE-2, ROUGE-L."""
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = {"rouge1": [], "rouge2": [], "rougeL": []}

    for pred, ref in zip(predictions, references):
        result = scorer.score(ref, pred)
        scores["rouge1"].append(result["rouge1"].fmeasure)
        scores["rouge2"].append(result["rouge2"].fmeasure)
        scores["rougeL"].append(result["rougeL"].fmeasure)

    return {k: round(sum(v) / len(v), 4) for k, v in scores.items()}


def compute_rating_metrics(
    predicted: list[float],
    actual: list[float]
) -> dict:
    """Compute RMSE and MAE for rating predictions."""
    n = len(predicted)
    rmse = math.sqrt(sum((p - a) ** 2 for p, a in zip(predicted, actual)) / n)
    mae = sum(abs(p - a) for p, a in zip(predicted, actual)) / n
    return {
        "rmse": round(rmse, 4),
        "mae": round(mae, 4)
    }



async def run_evaluation(n_samples: int = 50):
    pairs = load_evaluation_pairs(
        PROFILES_PATH, REVIEWS_PATH, BUSINESSES_PATH,
        n_samples=n_samples
    )

    if not pairs:
        print("No evaluation pairs found.")
        return

    print(f"\nRunning Task A evaluation on {len(pairs)} samples...")

    predictions = []
    references = []
    predicted_ratings = []
    actual_ratings = []

    async with httpx.AsyncClient() as client:
        for i, pair in enumerate(pairs):
            print(f"  [{i+1}/{len(pairs)}] user: {pair['user_id'][:8]}...")
            result = await call_task_a(client, pair)

            if result:
                predictions.append(result["generated_review"])
                references.append(pair["ground_truth_review"])
                predicted_ratings.append(result["predicted_stars"])
                actual_ratings.append(pair["ground_truth_stars"])

    if not predictions:
        print("No successful predictions.")
        return

    print(f"\nSuccessful evaluations: {len(predictions)}/{len(pairs)}")

    # ROUGE
    print("\nComputing ROUGE scores...")
    rouge = compute_rouge(predictions, references)
    print(f"  ROUGE-1:  {rouge['rouge1']}")
    print(f"  ROUGE-2:  {rouge['rouge2']}")
    print(f"  ROUGE-L:  {rouge['rougeL']}")

    # BERTScore
    print("\nComputing BERTScore...")
    P, R, F1 = bert_score(predictions, references, lang="en", verbose=False)
    bert_f1 = round(F1.mean().item(), 4)
    print(f"  BERTScore F1: {bert_f1}")

    # rating metrics
    print("\nComputing rating metrics...")
    rating_metrics = compute_rating_metrics(predicted_ratings, actual_ratings)
    print(f"  RMSE: {rating_metrics['rmse']}")
    print(f"  MAE:  {rating_metrics['mae']}")

    # Summary
    results = {
        "n_samples": len(predictions),
        "rouge": rouge,
        "bert_score_f1": bert_f1,
        "rating_rmse": rating_metrics["rmse"],
        "rating_mae": rating_metrics["mae"]
    }

    output_path = "data/processed/eval_task_a.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")
    print("\n=== TASK A EVALUATION SUMMARY ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run_evaluation(n_samples=args.samples))