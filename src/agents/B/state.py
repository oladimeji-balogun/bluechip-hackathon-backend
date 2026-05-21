from typing import TypedDict, Optional
from src.schemas.user_profile import UserProfile, TaskBResponse

class TaskBState(TypedDict): 
    # inputs
    profile: UserProfile
    context: Optional[str]
    domain: Optional[str]
    top_k: int
    nigerian_mode: bool 
    conversation_history: list[dict]

    # intermediate results to be updated as graph progresses
    user_analysis: Optional[dict]
    strategy: Optional[str]
    candidates: Optional[list[str]]
    ranked_output: Optional[dict]

    cold_start_used: bool
    cross_domain_used: bool 

    result: Optional[TaskBResponse]
    error: Optional[str]