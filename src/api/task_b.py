from fastapi import APIRouter, HTTPException
from src.schemas.user_profile import TaskBRequest, TaskBResponse
from src.agents.B.graph import agent_b_graph
from src.core.profile_store import ProfileStore

router = APIRouter()


@router.post("/recommend", response_model=TaskBResponse)
async def recommend(request: TaskBRequest) -> TaskBResponse:
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
        "context": request.context,
        "domain": request.domain,
        "top_k": request.top_k,
        "nigerian_mode": request.nigerian_mode,
        "conversation_history": request.conversation_history,
        "user_analysis": None,
        "strategy": None,
        "candidates": None,
        "ranked_output": None,
        "cold_start_used": False,
        "cross_domain_used": False,
        "result": None,
        "error": None,
    }

    # run graph
    final_state = await agent_b_graph.ainvoke(initial_state)

    # handle errors
    if final_state.get("error"):
        raise HTTPException(
            status_code=500,
            detail=final_state["error"]
        )

    return final_state["result"]