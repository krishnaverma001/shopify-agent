from langgraph.graph import StateGraph, END
from app.agents.state import ConversationState


def build_graph():
    from app.agents.nodes.supervisor import supervisor_node, route_after_supervisor
    from app.agents.nodes.query_understanding import query_understanding_node
    from app.agents.nodes.retrieval import retrieval_node
    from app.agents.nodes.result_evaluator import result_evaluator_node, route_after_evaluator
    from app.agents.nodes.expander import expander_node
    from app.agents.nodes.clarifier import clarifier_node
    from app.agents.nodes.responder import responder_node, no_results_node
    from app.agents.nodes.reset import reset_node
    from app.agents.nodes.details_similar import details_node, similar_node, general_respond_node
    from app.agents.nodes.compare import compare_node

    graph = StateGraph(ConversationState)

    graph.add_node("supervisor",          supervisor_node)
    graph.add_node("query_understanding", query_understanding_node)
    graph.add_node("retrieval",           retrieval_node)
    graph.add_node("result_evaluator",    result_evaluator_node)
    graph.add_node("expander",            expander_node)
    graph.add_node("clarifier",           clarifier_node)
    graph.add_node("responder",           responder_node)
    graph.add_node("details",             details_node)
    graph.add_node("similar",             similar_node)
    graph.add_node("compare",             compare_node)
    graph.add_node("general_respond",     general_respond_node)
    graph.add_node("no_results",          no_results_node)
    graph.add_node("reset",               reset_node)  

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "new_search": "query_understanding",
            "refine":     "query_understanding",
            "details":    "details",
            "similar":    "similar",
            "compare":    "compare",
            "respond":    "general_respond",
            "reset":      "reset",               
        },
    )

    graph.add_edge("query_understanding", "retrieval")
    graph.add_edge("retrieval",           "result_evaluator")

    graph.add_conditional_edges(
        "result_evaluator",
        route_after_evaluator,
        {
            "respond": "responder",
            "expand":  "expander",
            "clarify": "clarifier",
            "no_results": "no_results",
        },
    )

    graph.add_edge("expander", "retrieval")

    graph.add_edge("responder",       END)
    graph.add_edge("clarifier",       END)
    graph.add_edge("details",         END)
    graph.add_edge("similar",         END)
    graph.add_edge("compare",         END)
    graph.add_edge("general_respond", END)
    graph.add_edge("no_results",      END)
    graph.add_edge("reset",           END)

    return graph.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph