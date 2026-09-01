"""
app/agents/outcome.py — Outcome Detection Node for Phase 4.
"""
from typing import Any, Dict
from app.graph.state import RecoveryState
from app.agents.schemas import RecoveryOutcome, RecoverySignal
import logging
import datetime

logger = logging.getLogger(__name__)


def outcome_node(state: RecoveryState) -> Dict[str, Any]:
    """
    Analyzes the SimulationEngine's action_result and categorizes it.
    Emits a RecoverySignal and updates the outcome_history.
    """
    action_result = state.get("action_result", {})
    action_type = state.get("action_request", {}).get("action_type", "unknown")
    simulated_outcome = action_result.get("simulated_outcome", "")
    customer_response = action_result.get("customer_response", "")
    success = action_result.get("success", False)

    is_terminal = False
    escalate = False
    outcome_category = "unknown"
    signal_type = "unknown_signal"
    details = ""

    if simulated_outcome == "recovery_successful":
        outcome_category = "recovered"
        signal_type = "success"
        is_terminal = True
        details = "Payment successfully recovered."
        
    elif simulated_outcome == "recovery_failed":
        # In a real app we'd look closer. Here we treat all retries that fail as transient if we are under limits.
        outcome_category = "failed_transient"
        signal_type = "transient_failure"
        details = "Retry attempt failed."

    elif simulated_outcome == "customer_notified" or simulated_outcome == "reminder_sent":
        if customer_response:
            outcome_category = "customer_responded"
            signal_type = "customer_response"
            details = f"Customer responded: {customer_response}"
        else:
            outcome_category = "customer_did_not_respond"
            signal_type = "no_response"
            details = "Action executed, but no immediate customer response."

    elif simulated_outcome == "recovery_stopped":
        outcome_category = "failed_permanent"
        signal_type = "permanent_failure"
        is_terminal = True
        details = "Recovery explicitly stopped (e.g. by policy or max attempts)."

    elif simulated_outcome == "escalated":
        outcome_category = "failed_permanent"
        signal_type = "permanent_failure"
        is_terminal = True
        escalate = True
        details = "Case escalated to human."

    outcome = RecoveryOutcome(
        outcome_category=outcome_category,
        is_terminal=is_terminal,
        escalate_to_human=escalate,
        details=details
    )

    signal = RecoverySignal(
        signal_type=signal_type,
        timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
        source_action=action_type,
        context={"outcome": simulated_outcome, "customer_response": customer_response}
    )
    
    # Save to history
    outcome_history = list(state.get("outcome_history") or [])
    outcome_history.append(outcome.model_dump())

    # Log to DB Event sourcing
    from app.db.state.db import get_session
    from app.db.state.models import RecoveryCase, RecoveryEvent
    with get_session() as db:
        case = db.query(RecoveryCase).filter_by(payment_id=state.get("payment_id")).first()
        if case:
            event = RecoveryEvent(
                case_id=case.case_id,
                event_type="recovery_signal",
                agent_name="outcome",
                event_data=signal.model_dump()
            )
            db.add(event)
            db.commit()

    return {
        "latest_outcome": outcome.model_dump(),
        "recovery_signal": signal_type,
        "outcome_history": outcome_history,
        "messages": [{
            "role": "system",
            "content": f"Outcome Detected: {outcome_category} (Terminal: {is_terminal}). Signal: {signal_type}."
        }]
    }
