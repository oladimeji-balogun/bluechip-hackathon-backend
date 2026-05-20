from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ReviewTone(str, Enum):
    ENTHUSIASTIC = "enthusiastic"
    CRITICAL = "critical"
    BALANCED = "balanced"
    CASUAL = "casual"
    VERBOSE = "verbose"


class UserTier(str, Enum):
    COLD = "cold"        # fewer than 5 reviews
    LIGHT = "light"      # 5-20 reviews
    ACTIVE = "active"    # 21-100 reviews
    POWER = "power"      # 100+ reviews


class RatingBehaviour(BaseModel):
    average_stars: float = Field(..., ge=1.0, le=5.0)
    rating_std: float = Field(..., ge=0.0)
    tends_to_inflate: bool      # average > 3.8
    tends_to_deflate: bool      # average < 2.8
    distribution: dict[str, int]  # {"1": 3, "2": 5, "3": 10, "4": 20, "5": 30}


class WritingStyle(BaseModel):
    avg_review_length: int
    tone: ReviewTone
    uses_pidgin: bool = False
    common_phrases: list[str] = []
    uses_emoji: bool = False
    formality_score: float = Field(default=0.5, ge=0.0, le=1.0)


class CategoryPreference(BaseModel):
    top_categories: list[str] = []
    avoided_categories: list[str] = []
    cross_domain_signals: list[str] = []


class ReviewHistoryItem(BaseModel):
    item_id: str
    item_name: str
    category: str
    stars_given: float
    review_snippet: str     # first 300 chars only — keeps LLM context lean
    date: str


class NigerianContext(BaseModel):
    is_nigerian_context: bool = False
    local_references: list[str] = []
    pidgin_vocabulary: list[str] = []
    price_sensitivity: str = "medium"   # low / medium / high



class UserProfile(BaseModel):
    user_id: str
    name: Optional[str] = None
    tier: UserTier

    total_reviews: int
    rating_behaviour: RatingBehaviour
    writing_style: WritingStyle
    category_preference: CategoryPreference
    review_history: list[ReviewHistoryItem] = []   # capped at 20

    useful_votes: int = 0
    fans: int = 0
    elite_years: list[int] = []

    nigerian_context: NigerianContext = Field(default_factory=NigerianContext)
    profile_built_from_n_reviews: int
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class ItemMetadata(BaseModel):
    item_id: str
    name: str
    category: str
    subcategories: list[str] = []
    avg_community_rating: Optional[float] = None
    description: Optional[str] = None
    price_range: Optional[str] = None
    attributes: dict = {}


class TaskARequest(BaseModel):
    user_id: Optional[str] = None
    user_profile: Optional[UserProfile] = None
    item: ItemMetadata
    nigerian_mode: bool = False


class TaskAResponse(BaseModel):
    predicted_stars: float
    predicted_stars_rounded: int
    generated_review: str
    confidence: float
    reasoning: str


class RecommendationItem(BaseModel):
    rank: int
    item_id: str
    item_name: str
    category: str
    predicted_rating: float
    relevance_score: float
    explanation: str
    nigerian_relevance_note: Optional[str] = None


class TaskBRequest(BaseModel):
    user_id: Optional[str] = None
    user_profile: Optional[UserProfile] = None
    context: Optional[str] = None
    domain: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=50)
    nigerian_mode: bool = False
    conversation_history: list[dict] = []


class TaskBResponse(BaseModel):
    recommendations: list[RecommendationItem]
    reasoning: str
    cold_start_used: bool = False
    cross_domain_used: bool = False