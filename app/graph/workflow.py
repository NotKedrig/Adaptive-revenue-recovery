"""
app/graph/workflow.py — LangGraph workflow (Phase 2).

Current graph: Payment Event → Intake → Diagnosis → END

The graph routes based on eligibility after intake and produces a
terminal diagnosis state.
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import RecoveryState
from app.agents.intake import intake_node
from app.agents.diagnosis import diagnosis_node

# Singleton checkpointer to preserve multi-turn state across the app's lifetime
_memory_saver = MemorySaver()


def _route_after_intake(state: RecoveryState) -> str:
    """Route after intake: if eligible, proceed to diagnosis; otherwise end."""
    case_status = state.get("case_status", "")
    if case_status == "intake_complete":
        return "diagnosis"
    # Non-eligible cases (already recovered/failed/escalated) go straight to END
    return END


def build_graph():
    """
    Builds and compiles the LangGraph StateGraph for the AI Revenue Recovery POC.

    Phase 2 flow:
        START → intake → [eligible?] → diagnosis → END
                                    → END (not eligible)
    """
    workflow = StateGraph(RecoveryState)

    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("diagnosis", diagnosis_node)

    # Entry point
    workflow.add_edge(START, "intake")

    # Conditional routing after intake
    workflow.add_conditional_edges(
        "intake",
        _route_after_intake,
        {
            "diagnosis": "diagnosis",
            END: END,
        }
    )

    # Diagnosis is terminal for now (Phase 2)
    workflow.add_edge("diagnosis", END)

    return workflow.compile(checkpointer=_memory_saver)
