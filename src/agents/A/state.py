from typing import TypedDict, Optional
from src.schemas.user_profile import UserProfile, ItemMetadata, TaskAResponse

class TaskAState(TypedDict): 
    # inputs
    profile: UserProfile
    item: ItemMetadata
    nigerian_mode: bool

    # itermediate results filled as graph A progresses
    user_analysis: Optional[dict]
    item_analysis: Optional[dict]
    predicted_stars: Optional[float]
    rating_reasoning: Optional[str]
    generated_review: Optional[str]

    # outputs
    result: Optional[TaskAResponse]
    error: Optional[str]