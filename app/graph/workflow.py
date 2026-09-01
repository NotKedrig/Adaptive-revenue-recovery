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
from app.agents.outcome import outcome_node
from app.agents.adaptive_planner import adaptive_planner_node


def route_intake(state: RecoveryState) -> str:
    """Conditional routing from intake based on eligibility."""
    if state.get("case_status") == "intake_complete":
        return "diagnosis"
    return END

def route_after_outcome(state: RecoveryState) -> str:
    """Conditional routing after outcome detection."""
    latest = state.get("latest_outcome", {})
    if latest.get("is_terminal", False):
        return END
    
    # Bounded Loop Guard: Absolute maximum iteration limit to prevent infinite loops
    attempt_count = state.get("attempt_count", 0)
    max_attempts = state.get("max_attempts", 3)
    if attempt_count >= max_attempts + 2:  # allow a couple extra for purely communication attempts
        return END

    return "adaptive_planner"

def route_after_policy(state: RecoveryState) -> str:
    """Conditional routing after policy validation."""
    decision = state.get("policy_decision", {})
    # If the policy guard explicitly stops recovery, we exit immediately
    if not decision.get("allowed") and decision.get("mutated_action") == "stop_recovery":
        return "action" # Let the action node record the stopped action, then outcome will terminate
    return "action"


def build_graph() -> StateGraph:
    """
    Builds and compiles the LangGraph StateGraph for the AI Revenue Recovery POC.

    Phase 4 flow (Adaptive Cyclic Loop):
        START → intake → [eligible?] → diagnosis → strategy 
          → policy → action → outcome → [terminal?] → END
                                      → adaptive_planner ⤴ (loops back to policy)
    """
    workflow = StateGraph(RecoveryState)

    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("diagnosis", diagnosis_node)
    workflow.add_node("strategy", strategy_node)
    workflow.add_node("policy", policy_node)
    workflow.add_node("action", action_node)
    workflow.add_node("outcome", outcome_node)
    workflow.add_node("adaptive_planner", adaptive_planner_node)

    # Set entry point
    workflow.set_entry_point("intake")

    # Add edges
    workflow.add_conditional_edges("intake", route_intake, {"diagnosis": "diagnosis", END: END})
    workflow.add_edge("diagnosis", "strategy")
    workflow.add_edge("strategy", "policy")
    
    workflow.add_conditional_edges("policy", route_after_policy, {"action": "action"})
    
    workflow.add_edge("action", "outcome")
    
    workflow.add_conditional_edges(
        "outcome",
        route_after_outcome,
        {
            END: END,
            "adaptive_planner": "adaptive_planner"
        }
    )
    
    workflow.add_edge("adaptive_planner", "policy")

    # Compile the graph
    return workflow.compile()
