from langgraph.graph import StateGraph, START, END
from .nodes import AgentA
from .state import TaskAState

# the coditional logic to decide whether to add nigerian context or not
def should_apply_nigerian(state: TaskAState) -> str: 
    if state["error"]: 
        return "build_response"
    
    if state["nigerian_mode"] or state["profile"].nigerian_context.is_nigerian_context: 
        return "apply_nigerian_context"
    return "build_response"


def build_agent_a_graph() -> StateGraph: 
    agent = AgentA()
    graph = StateGraph(TaskAState)

    # registering the graph nodess
    graph.add_node("analyze_user", agent.analyze_user)
    graph.add_node("analyze_item", agent.analyze_item)
    graph.add_node("predict_rating", agent.predict_rating)
    graph.add_node("generate_review", agent.generate_review)
    graph.add_node("apply_nigerian", agent.apply_nigerian_context)
    graph.add_node("build_response", agent.build_response)

    # entry poing
    graph.set_entry_point("analyze_user")

    # adding the edges
    graph.add_edge("analyze_user", "analyze_item")
    graph.add_edge("analyze_item", "predict_rating")
    graph.add_edge("predict_rating", "generate_review")
    
    # the conditional edge
    graph.add_conditional_edges(
        "generate_review", 
        should_apply_nigerian, 
        {
            "apply_nigerian": "apply_nigerian", 
            "build_response": "build_response"
        }
    )

    graph.add_edge("apply_nigerian", "build_response")
    graph.add_edge("build_respnse", END)

    return graph.compile()



agent_a_graph = build_agent_a_graph()


    