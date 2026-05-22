from langgraph.graph import StateGraph, START, END 
from .nodes import AgentB 
from .state import TaskBState


# routing functions
def route_strategy(state: TaskBState) -> str:
    if state.get("error"):
        return "build_response"
    
    # hard override for cold start so as no to trust the LLM strategy
    profile = state["profile"]

    print(f"DEBUG tier: {profile.tier}, reviews: {profile.total_reviews}")
    
    if profile.tier == "cold" or profile.total_reviews < 5:
        return "popularity_fallback"
    

    
    strategy = state.get("strategy", "preference_retrieval")
    if strategy == "popularity_fallback":
        return "popularity_fallback"
    if strategy == "cross_domain_retrieval":
        return "cross_domain_retrieval"
    return "preference_retrieval"


def route_after_retrieval(state: TaskBState) -> str:
    if state.get("error"):
        return "build_response"
    candidates = state.get("candidates", [])
    if not candidates:
        state["error"] = "Retrieval returned no candidates"
        return "build_response"
    return "rank_candidates"

def build_graph_b(): 
    agent = AgentB()
    graph = StateGraph(TaskBState)

    # register the nodes 
    graph.add_node("analyze_user", agent.analyze_user)
    graph.add_node("popularity_fallback", agent.popularity_fallback)
    graph.add_node("cross_domain_retrieval", agent.cross_domain_retrieval)
    graph.add_node("preference_retrieval", agent.preference_retrieval)
    graph.add_node("rank_candidates", agent.rank_candidates)
    graph.add_node("apply_context", agent.apply_context)
    graph.add_node("build_response", agent.build_response)

    # entry point 
    graph.set_entry_point("analyze_user")

    # graph edges 
    graph.add_conditional_edges(
        "analyze_user",
        route_strategy,
        {
            "popularity_fallback": "popularity_fallback",
            "cross_domain_retrieval": "cross_domain_retrieval",
            "preference_retrieval": "preference_retrieval",
            "build_response": "build_response",
        }
    )

    graph.add_conditional_edges(
        "preference_retrieval", 
        route_after_retrieval, 
        {
            "rank_candidates": "rank_candidates", 
            "build_response": "build_response"
        }
    )

    graph.add_conditional_edges(
        "cross_domain_retrieval", 
        route_after_retrieval, 
        {
            "rank_candidates": "rank_candidates", 
            "build_response": "build_response"
        }
    )

    graph.add_conditional_edges(
        "popularity_fallback", 
        route_after_retrieval, 
        {
            "rank_candidates": "rank_candidates", 
            "build_response": "build_response"
        }
    )

    graph.add_edge("rank_candidates", "apply_context")
    graph.add_edge("apply_context", "build_response")
    graph.add_edge("build_response", END)

    return graph.compile()


agent_b_graph = build_graph_b()