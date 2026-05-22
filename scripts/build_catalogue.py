"""
Business Catalogue Builder
==========================
Processes Yelp business.json into a lean catalogue
used by the retrieval nodes.

Usage:
    python -m scripts.build_catalogue
"""

import json
from pathlib import Path


def build_catalogue(
    businesses_path: str,
    output_path: str,
    min_reviews: int = 10,
    is_open_only: bool = True
) -> None:

    print("Building business catalogue...")
    catalogue = {}

    with open(businesses_path) as f:
        for line in f:
            biz = json.loads(line)

            # Filter low-quality businesses
            if biz.get("review_count", 0) < min_reviews:
                continue
            if is_open_only and biz.get("is_open", 0) == 0:
                continue

            # Parse categories
            cats = biz.get("categories") or ""
            if isinstance(cats, str):
                cats = [c.strip() for c in cats.split(",") if c.strip()]

            if not cats:
                continue

            # Parse price range
            attrs = biz.get("attributes") or {}
            price_raw = attrs.get("RestaurantsPriceRange2")
            price = None
            if price_raw and str(price_raw).strip('"').isdigit():
                price = "$" * int(str(price_raw).strip('"'))

            catalogue[biz["business_id"]] = {
                "business_id": biz["business_id"],
                "name": biz["name"],
                "categories": cats,
                "primary_category": cats[0] if cats else "General",
                "city": biz.get("city", ""),
                "state": biz.get("state", ""),
                "stars": biz.get("stars", 0.0),
                "review_count": biz.get("review_count", 0),
                "price_range": price,
                "is_open": biz.get("is_open", 0),
                # Search text — what BM25 indexes
                "search_text": f"{biz['name']} {' '.join(cats)} {biz.get('city', '')}"
            }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(catalogue, f)

    print(f"Done. {len(catalogue)} businesses written to {output_path}")


if __name__ == "__main__":
    build_catalogue(
        businesses_path="data/raw/yelp_academic_dataset_business.json",
        output_path="data/processed/business_catalogue.json",
        min_reviews=10,
        is_open_only=True
    )