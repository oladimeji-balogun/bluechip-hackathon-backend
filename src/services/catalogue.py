"""
Business Catalogue + BM25 Search
==================================
Loads the business catalogue and provides fast BM25 search
for the retrieval nodes in Task B.

Usage:
    from src.services.catalogue import BusinessCatalogue
    catalogue = BusinessCatalogue()
    catalogue.load("data/processed/business_catalogue.json")
    results = catalogue.search("Nigerian food Lagos", top_k=20)
"""

import json
from pathlib import Path
from rank_bm25 import BM25Okapi


class BusinessCatalogue:
    _businesses: dict = {}
    _bm25: BM25Okapi = None
    _index: list[str] = []   # ordered list of business_ids matching BM25 index
    _loaded: bool = False

    @classmethod
    def load(cls, path: str) -> None:
        p = Path(path)
        if not p.exists():
            print(f"WARNING: Business catalogue not found at {path}")
            return

        print("Loading business catalogue...")
        with open(p) as f:
            cls._businesses = json.load(f)

        print("Building BM25 index...")
        cls._index = list(cls._businesses.keys())
        corpus = [
            cls._businesses[bid]["search_text"].lower().split()
            for bid in cls._index
        ]
        cls._bm25 = BM25Okapi(corpus)
        cls._loaded = True
        print(f"Catalogue ready — {len(cls._businesses)} businesses indexed.")

    @classmethod
    def search(
        cls,
        query: str,
        top_k: int = 20,
        category_filter: str | None = None,
        min_stars: float = 3.5
    ) -> list[dict]:
        """
        BM25 search over business catalogue.

        Args:
            query: natural language query e.g. "Nigerian fast food Lagos"
            top_k: number of results to return
            category_filter: optional category to restrict results
            min_stars: minimum community rating

        Returns:
            List of business dicts ranked by relevance
        """
        if not cls._loaded or cls._bm25 is None:
            return []

        tokens = query.lower().split()
        scores = cls._bm25.get_scores(tokens)

        # pair scores with business IDs and sort
        scored = sorted(
            zip(scores, cls._index),
            key=lambda x: x[0],
            reverse=True
        )

        results = []
        for score, bid in scored:
            if len(results) >= top_k:
                break

            biz = cls._businesses[bid]

            # Apply filters
            if biz["stars"] < min_stars:
                continue
            if category_filter:
                cats_lower = [c.lower() for c in biz["categories"]]
                if not any(category_filter.lower() in c for c in cats_lower):
                    continue

            results.append({
                "item_id": biz["business_id"],
                "name": biz["name"],
                "category": biz["primary_category"],
                "description": f"{biz['name']} — {', '.join(biz['categories'][:3])} in {biz['city']}, {biz['state']}",
                "avg_rating": biz["stars"],
                "price_range": biz["price_range"] or "$$",
                "review_count": biz["review_count"]
            })

        return results

    @classmethod
    def get(cls, business_id: str) -> dict | None:
        return cls._businesses.get(business_id)

    @classmethod
    def count(cls) -> int:
        return len(cls._businesses)