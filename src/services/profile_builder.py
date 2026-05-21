import json
import statistics
from collections import Counter
from pathlib import Path

from src.schemas.user_profile import (
    UserProfile, RatingBehaviour, WritingStyle, CategoryPreference,
    ReviewHistoryItem, NigerianContext, ReviewTone, UserTier
)


NIGERIAN_FOOD_TERMS = {
    "suya", "jollof", "egusi", "pounded yam", "ofada", "amala",
    "buka", "pepper soup", "nkwobi", "eba", "garri", "akara",
    "moi moi", "ogbono", "afang", "isi ewu"
}

NIGERIAN_LOCATIONS = {
    "lagos", "abuja", "port harcourt", "ibadan", "kano", "enugu",
    "calabar", "warri", "benin city", "owerri", "uyo", "kaduna"
}

PIDGIN_MARKERS = {
    "e dey", "na so", "no be", "wetin", "wahala", "omo", "abeg",
    "correct", "sharp sharp", "how far", "e sweet", "pepper dem",
    "carry go", "sabi", "packaging"
}



def detect_tone(reviews: list[dict], avg_stars: float) -> ReviewTone:
    if not reviews:
        return ReviewTone.BALANCED

    avg_words = sum(len(r.get("text", "").split()) for r in reviews) / len(reviews)
    all_text = " ".join(r.get("text", "") for r in reviews).lower()
    exclamations = all_text.count("!")

    if avg_words > 150:
        return ReviewTone.VERBOSE
    if exclamations / len(reviews) > 3 and avg_stars > 3.5:
        return ReviewTone.ENTHUSIASTIC
    if avg_stars < 2.8:
        return ReviewTone.CRITICAL
    if avg_words < 40:
        return ReviewTone.CASUAL
    return ReviewTone.BALANCED


def extract_common_phrases(reviews: list[dict], top_n: int = 10) -> list[str]:
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "was", "is", "it", "i", "my", "we", "they",
        "this", "that", "have", "had", "be", "are", "not", "very", "so",
        "just", "get", "got", "here", "there", "from", "their", "our"
    }
    words = []
    for r in reviews:
        for w in r.get("text", "").lower().split():
            w = w.strip(".,!?\"'")
            if w not in STOPWORDS and len(w) > 3:
                words.append(w)
    return [word for word, _ in Counter(words).most_common(top_n)]


def detect_nigerian_context(reviews: list[dict]) -> NigerianContext:
    all_text = " ".join(r.get("text", "") for r in reviews).lower()
    local_refs = [t for t in NIGERIAN_FOOD_TERMS | NIGERIAN_LOCATIONS if t in all_text]
    pidgin = [p for p in PIDGIN_MARKERS if p in all_text]
    return NigerianContext(
        is_nigerian_context=len(local_refs) > 0 or len(pidgin) > 0,
        local_references=local_refs[:10],
        pidgin_vocabulary=pidgin[:10],
        price_sensitivity="medium"
    )


class ProfileBuilder:

    def build(
        self,
        user_record: dict,
        reviews: list[dict],
        businesses: dict[str, dict] | None = None
    ) -> UserProfile:

        reviews = sorted(reviews, key=lambda r: r.get("date", ""), reverse=True)
        recent = reviews[:20]
        n = len(reviews)

        # Rating behaviour
        stars = [r["stars"] for r in reviews if "stars" in r]
        avg = statistics.mean(stars) if stars else 3.0
        std = statistics.stdev(stars) if len(stars) > 1 else 0.0

        rating_behaviour = RatingBehaviour(
            average_stars=round(avg, 2),
            rating_std=round(std, 2),
            tends_to_inflate=avg > 3.8,
            tends_to_deflate=avg < 2.8,
            distribution=dict(Counter(str(int(s)) for s in stars))
        )

        # Writing style
        word_counts = [len(r.get("text", "").split()) for r in reviews]
        avg_len = int(statistics.mean(word_counts)) if word_counts else 0
        all_text = " ".join(r.get("text", "") for r in reviews)

        writing_style = WritingStyle(
            avg_review_length=avg_len,
            tone=detect_tone(reviews, avg),
            uses_pidgin=any(p in all_text.lower() for p in PIDGIN_MARKERS),
            common_phrases=extract_common_phrases(reviews),
            uses_emoji=any(ord(c) > 127 for c in all_text),
            formality_score=min(1.0, avg_len / 200)
        )

        # Category preferences
        cat_counter: Counter = Counter()
        avoided = []
        # for r in reviews:
        #     biz = (businesses or {}).get(r.get("business_id", ""), {})
        #     for cat in biz.get("categories", "").split(", "):
        #         cat = cat.strip()
        #         if cat:
        #             cat_counter[cat] += 1
        #             if r.get("stars", 3) <= 2:
        #                 avoided.append(cat)

        for r in reviews:
            biz = (businesses or {}).get(r.get("business_id", ""), {})
            cats = biz.get("categories") or []
            if isinstance(cats, str):
                cats = [c.strip() for c in cats.split(",")]
            for cat in cats:
                cat = cat.strip()
                if cat:
                    cat_counter[cat] += 1
                    if r.get("stars", 3) <= 2:
                        avoided.append(cat)

        category_preference = CategoryPreference(
            top_categories=[c for c, _ in cat_counter.most_common(10)],
            avoided_categories=list(set(avoided))[:5],
            cross_domain_signals=[c for c, _ in cat_counter.most_common(3)]
        )

        # Review history (lightweight)

        cats = biz.get("categories") or []
        if isinstance(cats, str):
            cats = [c.strip() for c in cats.split(",")]

        history = []
        for r in recent:
            biz = (businesses or {}).get(r.get("business_id", ""), {})
            history.append(ReviewHistoryItem(
                item_id=r.get("business_id", "unknown"),
                item_name=biz.get("name", "Unknown"),
                # category=biz.get("categories", "General").split(",")[0].strip(),
                category=cats[0] if cats else "General",
                stars_given=r.get("stars", 3),
                review_snippet=r.get("text", "")[:300],
                date=r.get("date", "")[:10]
            ))

        # Tier
        if n < 5:
            tier = UserTier.COLD
        elif n < 21:
            tier = UserTier.LIGHT
        elif n < 101:
            tier = UserTier.ACTIVE
        else:
            tier = UserTier.POWER

        return UserProfile(
            user_id=user_record.get("user_id", "unknown"),
            name=user_record.get("name"),
            tier=tier,
            total_reviews=n,
            rating_behaviour=rating_behaviour,
            writing_style=writing_style,
            category_preference=category_preference,
            review_history=history,
            useful_votes=user_record.get("useful", 0),
            fans=user_record.get("fans", 0),
            elite_years=user_record.get("elite", []) if isinstance(user_record.get("elite"), list) else [],
            nigerian_context=detect_nigerian_context(reviews),
            profile_built_from_n_reviews=n,
            confidence_score=round(min(1.0, n / 20), 2)
        )
    

# batch processing 
def build_profiles_from_yelp(
    users_path: str,
    reviews_path: str,
    businesses_path: str,
    output_path: str,
    limit: int | None = None
) -> None:

    print("Loading businesses...")
    businesses = {}
    with open(businesses_path) as f:
        for line in f:
            biz = json.loads(line)
            businesses[biz["business_id"]] = biz

    print("Loading reviews...")
    reviews_by_user: dict[str, list] = {}
    with open(reviews_path) as f:
        for i, line in enumerate(f):
            if limit and i >= limit * 10:
                break
            r = json.loads(line)
            uid = r.get("user_id")
            if uid:
                reviews_by_user.setdefault(uid, []).append(r)

    print("Building profiles...")
    builder = ProfileBuilder()
    profiles = {}
    with open(users_path) as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            user = json.loads(line)
            uid = user.get("user_id")
            profiles[uid] = builder.build(
                user,
                reviews_by_user.get(uid, []),
                businesses
            ).model_dump()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(profiles, f)
    print(f"Done. {len(profiles)} profiles written to {output_path}")


if __name__ == "__main__":
    build_profiles_from_yelp(
        users_path="data/raw/yelp_academic_dataset_user.json",
        reviews_path="data/raw/yelp_academic_dataset_review.json",
        businesses_path="data/raw/yelp_academic_dataset_business.json",
        output_path="data/processed/user_profiles.json",
        limit=10000
    )