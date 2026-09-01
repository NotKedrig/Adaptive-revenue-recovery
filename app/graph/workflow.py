"""
app/graph/workflow.py — LangGraph workflow (Phase 3).

Current graph: Payment Event → Intake → Diagnosis → Strategy → Policy → Action → END

The graph routes based on eligibility after intake and executes recovery steps.
"""
from langgraph.graph import StateGraph, START, END
from app.graph.state import RecoveryState
from app.agents.intake import intake_node
from app.agents.diagnosis import diagnosis_node
from app.agents.strategy import strategy_node
from app.agents.policy import policy_node
from app.agents.action import action_node


def route_intake(state: RecoveryState) -> str:
    """Conditional routing from intake based on eligibility."""
    if state.get("case_status") == "intake_complete":
        return "diagnosis"
    return END


def build_graph() -> StateGraph:
    """
    Builds and compiles the LangGraph StateGraph for the AI Revenue Recovery POC.

    Phase 3 flow:
        START → intake → [eligible?] → diagnosis → strategy → policy → action → END
                                    → END (not eligible)
    """
    workflow = StateGraph(RecoveryState)

    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("diagnosis", diagnosis_node)
    workflow.add_node("strategy", strategy_node)
    workflow.add_node("policy", policy_node)
    workflow.add_node("action", action_node)

    # Set entry point
    workflow.set_entry_point("intake")

    # Add edges
    workflow.add_conditional_edges(
        "intake",
        route_intake,
        {
            "diagnosis": "diagnosis",
            END: END
        }
    )
    workflow.add_edge("diagnosis", "strategy")
    workflow.add_edge("strategy", "policy")
    workflow.add_edge("policy", "action")
    workflow.add_edge("action", END)

    # Compile the graph (without Checkpointer to keep it simple for demo)
    return workflow.compile()
