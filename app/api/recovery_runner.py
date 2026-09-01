"""
Step the existing LangGraph recovery nodes one cycle at a time.

This does not reimplement diagnosis, strategy, policy, action, outcome, or
adaptive planning. It calls those nodes in the same order as
app.graph.workflow and persists enough state on the case so the operations
console can advance recovery without a full browser-refresh or graph rewrite.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from langgraph.graph import END

from app.agents.action import action_node
from app.agents.adaptive_planner import adaptive_planner_node
from app.agents.diagnosis import diagnosis_node
from app.agents.intake import intake_node
from app.agents.outcome import outcome_node
from app.agents.policy import policy_node
from app.agents.strategy import strategy_node
from app.graph.workflow import route_after_outcome, route_after_policy, route_intake

ACCUMULATE_KEYS = {
    "messages",
    "runtime_metadata",
    "strategy_history",
    "action_history",
    "outcome_history",
}

TERMINAL_STATUSES = {"recovered", "failed", "escalated", "closed"}


def merge_state(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Apply a node update using the same list-accumulation semantics as RecoveryState."""
    merged = dict(state)
    for key, value in update.items():
        if key in ACCUMULATE_KEYS:
            merged[key] = list(merged.get(key) or []) + list(value or [])
        else:
            merged[key] = value
    return merged


def initial_state(payment_id: str, failure_code: str, failure_reason: str) -> dict[str, Any]:
    return {
        "payment_id": payment_id,
        "failure_code": failure_code or "",
        "failure_reason": failure_reason or "",
        "messages": [],
        "runtime_metadata": [],
        "attempt_count": 0,
        "max_attempts": 3,
        "safety_cleared": False,
        "safety_flags": [],
        "simulated_time_hours": 0,
        "strategy_history": [],
        "action_history": [],
        "outcome_history": [],
    }


def can_advance(state: dict[str, Any] | None, case_status: str) -> bool:
    if case_status in TERMINAL_STATUSES:
        return False
    if not state:
        return True
    latest = state.get("latest_outcome") or {}
    if latest.get("is_terminal"):
        return False
    attempt_count = int(state.get("attempt_count") or 0)
    max_attempts = int(state.get("max_attempts") or 3)
    if attempt_count >= max_attempts + 2:
        return False
    return True


def run_cycle(state: dict[str, Any], *, first_cycle: bool) -> dict[str, Any]:
    """
    Execute one recovery cycle through the existing agent nodes.

    First cycle: intake → diagnosis → strategy → policy → action → outcome
    Later cycles: adaptive_planner → policy → action → outcome
    """
    current = deepcopy(state)

    if first_cycle:
        current = merge_state(current, intake_node(current))
        if route_intake(current) == END:
            return current
        current = merge_state(current, diagnosis_node(current))
        current = merge_state(current, strategy_node(current))
        current = merge_state(current, policy_node(current))
        if route_after_policy(current) == "action":
            current = merge_state(current, action_node(current))
            current = merge_state(current, outcome_node(current))
        return current

    if route_after_outcome(current) == END:
        return current

    current = merge_state(current, adaptive_planner_node(current))
    current = merge_state(current, policy_node(current))
    if route_after_policy(current) == "action":
        current = merge_state(current, action_node(current))
        current = merge_state(current, outcome_node(current))
    return current


def serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Drop non-essential bulky fields while keeping workflow-resume data."""
    skip = {"messages", "runtime_metadata"}
    return {key: value for key, value in state.items() if key not in skip}
