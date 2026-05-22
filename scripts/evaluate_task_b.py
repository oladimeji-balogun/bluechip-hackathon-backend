"""
Task B Evaluation
=================
Measures recommendation quality against held-out Yelp reviews.

Metrics:
- NDCG@10    : ranking quality — are relevant items ranked highly?
- Hit Rate@10: did any relevant item appear in top 10?
- Precision@10: what fraction of top 10 are relevant?

Strategy: leave-one-out
- For each user, hold out their highest-rated items
- Ask the agent to recommend for that user
- Check if held-out items appear in recommendations

Usage:
    python -m scripts.evaluate_task_b --samples 50
"""

import asyncio
import argparse
import json
import math
import random
import httpx


API_URL = "http://localhost:8000/api/v1/task-b/recommend"
PROFILES_PATH = "data/processed/user_profiles.json"
REVIEWS_PATH = "data/raw/yelp_academic_dataset_review.json"
BUSINESSES_PATH = "data/raw/yelp_academic_dataset_business.json"


def load_evaluation_data(
    profiles_path: str,
    reviews_path: str,
    businesses_path: str,
    n_samples: int = 50,
    min_reviews: int = 15
) -> list[dict]:
    """
    Build evaluation cases for Task B.

    Strategy:
    - Pick users with >= min_reviews
    - Hold out their highest rated items (4+ stars) not in profile history
    - These held-out items are the ground truth relevant items
    - We ask the agent to recommend and check if it surfaces them
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

    print("Building evaluation cases...")
    cases = []
    eligible = [
        uid for uid, p in profiles.items()
        if p["total_reviews"] >= min_reviews
    ]
    random.shuffle(eligible)

    for uid in eligible:
        if len(cases) >= n_samples:
            break

        profile = profiles[uid]
        all_reviews = reviews_by_user.get(uid, [])
        history_ids = {r["item_id"] for r in profile["review_history"]}

        # Held-out relevant items — rated 4+ stars, not in profile history
        relevant = [
            r for r in all_reviews
            if r.get("business_id") not in history_ids
            and float(r.get("stars", 0)) >= 4.0
        ]

        if len(relevant) < 2:
            continue

        # Get category from top categories for domain hint
        top_cats = profile["category_preference"]["top_categories"]
        domain = top_cats[0].lower() if top_cats else "restaurants"

        relevant_ids = {r["business_id"] for r in relevant}
        relevant_names = {}
        for r in relevant:
            biz = businesses.get(r["business_id"], {})
            relevant_names[r["business_id"]] = biz.get("name", "Unknown")

        cases.append({
            "user_id": uid,
            "domain": domain,
            "relevant_item_ids": list(relevant_ids),
            "relevant_item_names": relevant_names,
            "top_k": 10
        })

    print(f"Built {len(cases)} evaluation cases.")
    return cases



async def call_task_b(client: httpx.AsyncClient, case: dict) -> dict | None:
    """Call the Task B endpoint for one evaluation case."""
    payload = {
        "user_id": case["user_id"],
        "domain": case["domain"],
        "top_k": case["top_k"],
        "nigerian_mode": False,
        "conversation_history": []
    }
    try:
        response = await client.post(API_URL, json=payload, timeout=60.0)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error for user {case['user_id']}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None
    

def compute_ndcg(
    recommended_ids: list[str],
    relevant_ids: set[str],
    k: int = 10
) -> float:
    """
    Compute NDCG@k.

    NDCG rewards relevant items appearing higher in the ranking.
    A relevant item at rank 1 is worth more than one at rank 10.

    DCG  = sum(relevance_i / log2(rank_i + 1))
    IDCG = best possible DCG (all relevant items at top)
    NDCG = DCG / IDCG
    """
    dcg = 0.0
    for rank, item_id in enumerate(recommended_ids[:k], start=1):
        if item_id in relevant_ids:
            dcg += 1.0 / math.log2(rank + 1)

    # Ideal DCG — all relevant items ranked at the top
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    if idcg == 0:
        return 0.0
    return round(dcg / idcg, 4)


def compute_hit_rate(
    recommended_ids: list[str],
    relevant_ids: set[str],
    k: int = 10
) -> float:
    """
    Hit Rate@k — did at least one relevant item appear in top k?
    Binary: 1.0 if yes, 0.0 if no.
    """
    return 1.0 if any(i in relevant_ids for i in recommended_ids[:k]) else 0.0


def compute_precision(
    recommended_ids: list[str],
    relevant_ids: set[str],
    k: int = 10
) -> float:
    """
    Precision@k — what fraction of top k recommendations are relevant?
    """
    hits = sum(1 for i in recommended_ids[:k] if i in relevant_ids)
    return round(hits / k, 4)


async def run_evaluation(n_samples: int = 50):
    cases = load_evaluation_data(
        PROFILES_PATH, REVIEWS_PATH, BUSINESSES_PATH,
        n_samples=n_samples
    )

    if not cases:
        print("No evaluation cases found.")
        return

    print(f"\nRunning Task B evaluation on {len(cases)} samples...")

    ndcg_scores = []
    hit_rates = []
    precision_scores = []
    cold_start_count = 0
    cross_domain_count = 0

    async with httpx.AsyncClient() as client:
        for i, case in enumerate(cases):
            print(f"  [{i+1}/{len(cases)}] user: {case['user_id'][:8]}...")
            result = await call_task_b(client, case)

            # rate limit protection because of groq client
            await asyncio.sleep(25)


            if not result:
                continue

            # extract recommended item IDs
            # recommended_ids = [
            #     r["item_id"] for r in result.get("recommendations", [])
            # ]
            # relevant_ids = set(case["relevant_item_ids"])

            # ndcg_scores.append(compute_ndcg(recommended_ids, relevant_ids))
            # hit_rates.append(compute_hit_rate(recommended_ids, relevant_ids))
            # precision_scores.append(compute_precision(recommended_ids, relevant_ids))

            # extract recommended item IDs
            recommended_ids = [
                r["item_id"] for r in result.get("recommendations", [])
            ]
            relevant_ids = set(case["relevant_item_ids"])

            ndcg_scores.append(compute_ndcg(recommended_ids, relevant_ids))
            hit_rates.append(compute_hit_rate(recommended_ids, relevant_ids))
            precision_scores.append(compute_precision(recommended_ids, relevant_ids))


            if result.get("cold_start_used"):
                cold_start_count += 1
            if result.get("cross_domain_used"):
                cross_domain_count += 1

    if not ndcg_scores:
        print("No successful evaluations.")
        return

    n = len(ndcg_scores)
    results = {
        "n_samples": n,
        "ndcg_at_10": round(sum(ndcg_scores) / n, 4),
        "hit_rate_at_10": round(sum(hit_rates) / n, 4),
        "precision_at_10": round(sum(precision_scores) / n, 4),
        "cold_start_cases": cold_start_count,
        "cross_domain_cases": cross_domain_count,
    }

    output_path = "data/processed/eval_task_b.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {output_path}")
    print("\n=== TASK B EVALUATION SUMMARY ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run_evaluation(n_samples=args.samples))