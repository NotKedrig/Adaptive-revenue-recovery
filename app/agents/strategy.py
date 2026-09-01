"""
app/agents/strategy.py — Deterministic Planner for Revenue Recovery.
"""
from typing import Any, Dict
from app.graph.state import RecoveryState
from app.agents.schemas import RecoveryStrategy
import logging

logger = logging.getLogger(__name__)


def _plan_strategy(diagnosis_dict: Dict[str, Any], attempt_count: int) -> RecoveryStrategy:
    """
    Deterministic rule engine to map a diagnosis to a recovery strategy.
    """
    category = diagnosis_dict.get("failure_category", "unknown")
    recommended = diagnosis_dict.get("recommended_action", "")
    is_recoverable = diagnosis_dict.get("is_recoverable", False)

    if not is_recoverable or category.startswith("permanent_"):
        return RecoveryStrategy(
            action="request_new_payment_method",
            channel="email",
            retry_timing_hours=0,
            maximum_attempts=1,
            escalation_condition="immediate_stop",
            expected_outcome="customer_update_required",
            rationale=f"Permanent failure ({category}), cannot automatically retry."
        )

    if category == "transient_technical":
        # e.g., bank timeout, network error
        if attempt_count == 0:
            return RecoveryStrategy(
                action="immediate_retry",
                channel=None,  # silent backend retry
                retry_timing_hours=0,
                maximum_attempts=3,
                escalation_condition="max_attempts_reached",
                expected_outcome="successful_authorization",
                rationale="Transient technical issue. Immediate retry is optimal for first attempt."
            )
        else:
            return RecoveryStrategy(
                action="delayed_retry",
                channel=None,
                retry_timing_hours=4,  # wait 4 hours for subsequent retries
                maximum_attempts=3,
                escalation_condition="max_attempts_reached",
                expected_outcome="successful_authorization",
                rationale="Subsequent transient failure. Delaying retry to allow network recovery."
            )

    if category == "transient_customer":
        # e.g., insufficient funds
        return RecoveryStrategy(
            action="delayed_retry",
            channel="sms",  # notify customer
            retry_timing_hours=48,  # typically wait for salary/deposit
            maximum_attempts=3,
            escalation_condition="max_attempts_reached",
            expected_outcome="funds_available",
            rationale="Insufficient funds requires time for customer deposit. SMS reminder sent."
        )

    # Fallback default
    return RecoveryStrategy(
        action=recommended if recommended else "escalate_to_human",
        channel="email",
        retry_timing_hours=24,
        maximum_attempts=1,
        escalation_condition="unknown_failure_type",
        expected_outcome="human_review",
        rationale="Fallback strategy triggered due to unhandled failure category."
    )


def strategy_node(state: RecoveryState) -> Dict[str, Any]:
    """
    LangGraph node for Recovery Strategy Planning.
    """
    diagnosis = state.get("diagnosis", {})
    attempt_count = state.get("attempt_count", 0)

    logger.info(
        "Strategy node processing",
        extra={"payment_id": state.get("payment_id"), "attempt_count": attempt_count}
    )

    strategy = _plan_strategy(diagnosis, attempt_count)

    return {
        "strategy": strategy.model_dump(),
        "messages": [{
            "role": "system",
            "content": f"Strategy selected: {strategy.action} via {strategy.channel or 'backend'}. Rationale: {strategy.rationale}"
        }]
    }
