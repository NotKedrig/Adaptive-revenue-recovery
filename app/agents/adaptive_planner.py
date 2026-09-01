"""
app/agents/adaptive_planner.py — Adaptive Re-planner Node for Phase 4.
"""
from typing import Any, Dict
from app.graph.state import RecoveryState
from app.agents.schemas import RecoveryStrategy
import logging

logger = logging.getLogger(__name__)


def adaptive_planner_node(state: RecoveryState) -> Dict[str, Any]:
    """
    Analyzes historical actions and outcomes to devise a new strategy.
    """
    diagnosis = state.get("diagnosis", {})
    attempt_count = state.get("attempt_count", 0)
    max_attempts = state.get("max_attempts", 3)
    
    strategy_history = state.get("strategy_history", [])
    outcome_history = state.get("outcome_history", [])
    latest_outcome = state.get("latest_outcome", {})
    recovery_signal = state.get("recovery_signal", "")
    
    # Identify what we did last
    previous_strategy = strategy_history[-1] if strategy_history else {}
    previous_action = previous_strategy.get("action", "unknown")
    
    logger.info(
        "Adaptive Planner processing",
        extra={
            "payment_id": state.get("payment_id"),
            "attempt": attempt_count,
            "signal": recovery_signal
        }
    )

    new_action = "stop_recovery"
    new_channel = None
    new_delay = 0
    rationale = ""
    escalation_condition = "max_attempts_reached"

    # --- Adaptive Logic ---
    if recovery_signal == "success":
        # Should not reach here if outcome handles routing, but just in case
        new_action = "stop_recovery"
        rationale = "Payment already recovered."

    elif recovery_signal == "permanent_failure":
        new_action = "escalate_to_human"
        rationale = "Permanent failure detected, escalating."

    elif attempt_count >= max_attempts:
        new_action = "escalate_to_human"
        rationale = f"Exhausted maximum attempts ({max_attempts}). Escalating."

    elif recovery_signal == "customer_response":
        # E.g. they clicked the link but payment didn't process, or they said they updated it.
        # So we can try an immediate retry to see if it clears now.
        new_action = "immediate_retry"
        rationale = "Customer responded to notification. Attempting immediate retry to capture funds."

    elif recovery_signal == "no_response":
        # We notified them but no response. 
        if previous_action in ["payment_reminder", "payment_method_update_request"]:
            if previous_strategy.get("channel") == "email":
                # Escalate channel to SMS
                new_action = "payment_reminder"
                new_channel = "sms"
                rationale = "No response via email. Escalating communication channel to SMS."
            else:
                # Already SMS, let's just wait and retry
                new_action = "delayed_retry"
                new_delay = 24
                rationale = "No response via SMS. Falling back to delayed background retry."
        else:
            new_action = "delayed_retry"
            new_delay = 24
            rationale = "No customer response detected, scheduling delayed retry."

    elif recovery_signal == "transient_failure":
        # E.g. our immediate retry failed
        if previous_action == "immediate_retry":
            # If it's a customer issue (NSF), remind them
            if diagnosis.get("failure_category") == "transient_customer":
                new_action = "payment_reminder"
                new_channel = "email"
                rationale = "Immediate retry failed for transient customer issue. Sending email reminder."
            else:
                # Technical issue, back off and retry later
                new_action = "delayed_retry"
                new_delay = 12
                rationale = "Immediate retry failed for technical issue. Applying exponential backoff (12h)."
        elif previous_action == "delayed_retry":
            # Still failing, escalate to asking customer
            new_action = "payment_method_update_request"
            new_channel = "email"
            rationale = "Delayed retry failed. Requesting customer to update payment method."
        else:
            new_action = "delayed_retry"
            new_delay = 24
            rationale = "Transient failure on unknown action. Scheduling delayed retry."
            
    else:
        # Fallback
        new_action = "escalate_to_human"
        rationale = f"Unknown recovery signal '{recovery_signal}'. Escalating to human."

    strategy = RecoveryStrategy(
        action=new_action,
        channel=new_channel,
        retry_timing_hours=new_delay,
        maximum_attempts=max_attempts,
        escalation_condition=escalation_condition,
        expected_outcome="adaptive_resolution",
        rationale=rationale
    )
    
    # Audit trail for the strategy transition
    transition_record = {
        "previous_strategy_action": previous_action,
        "latest_outcome_category": latest_outcome.get("outcome_category"),
        "recovery_signal": recovery_signal,
        "new_strategy_action": new_action,
        "transition_reason": rationale
    }

    from app.db.state.db import get_session
    from app.db.state.models import RecoveryCase, AuditLog, RecoveryEvent
    with get_session() as db:
        case = db.query(RecoveryCase).filter_by(payment_id=state.get("payment_id")).first()
        if case:
            audit = AuditLog(
                action="adaptive_strategy_transition",
                resource_type="recovery_case",
                resource_id=case.id,
                details=transition_record
            )
            db.add(audit)
            
            event = RecoveryEvent(
                case_id=case.case_id,
                event_type="adaptive_transition",
                agent_name="adaptive_planner",
                event_data=transition_record
            )
            db.add(event)
            db.commit()

    return {
        "strategy": strategy.model_dump(),
        "messages": [{
            "role": "system",
            "content": f"Adaptive transition: [{previous_action}] -> ({recovery_signal}) -> [{new_action}]. Reason: {rationale}"
        }]
    }
