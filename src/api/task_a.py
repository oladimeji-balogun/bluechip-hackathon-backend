from fastapi import APIRouter, HTTPException
from src.schemas.user_profile import TaskARequest, TaskAResponse
from src.agents.A.graph import agent_a_graph
from src.core.profile_store import ProfileStore

router = APIRouter()


@router.post("/generate", response_model=TaskAResponse)
async def generate_review(request: TaskARequest) -> TaskAResponse:
    # resolve profile
    profile = request.user_profile
    if profile is None:
        if request.user_id is None:
            raise HTTPException(
                status_code=400,
                detail="Provide either user_id or user_profile."
            )
        profile = ProfileStore.get(request.user_id)
        if profile is None:
            raise HTTPException(
                status_code=404,
                detail=f"User '{request.user_id}' not found."
            )

    # build initial state
    initial_state = {
        "profile": profile,
        "item": request.item,
        "nigerian_mode": request.nigerian_mode,
        "user_analysis": None,
        "item_analysis": None,
        "predicted_stars": None,
        "rating_reasoning": None,
        "generated_review": None,
        "result": None,
        "error": None,
    }

    # run graph
    final_state = await agent_a_graph.ainvoke(initial_state)

    # handle errors
    if final_state.get("error"):
        raise HTTPException(
            status_code=500,
            detail=final_state["error"]
        )

    return final_state["result"]