"""
app/agents/policy.py — Safety Guard for Recovery Execution.
"""
from typing import Any, Dict
from app.graph.state import RecoveryState
from app.agents.schemas import PolicyDecision
import logging

logger = logging.getLogger(__name__)


def _evaluate_policy(strategy_dict: Dict[str, Any], state: RecoveryState) -> PolicyDecision:
    """
    Evaluates the proposed strategy against strict safety rules.
    """
    action = strategy_dict.get("action", "")
    max_attempts = strategy_dict.get("maximum_attempts", 3)
    attempt_count = state.get("attempt_count", 0)
    diagnosis = state.get("diagnosis", {})
    payment_id = state.get("payment_id")
    
    # Rule 1: Max Attempts Exhausted
    if attempt_count >= max_attempts:
        return PolicyDecision(
            allowed=False,
            reason=f"Maximum attempts ({max_attempts}) reached or exceeded (current: {attempt_count}).",
            mutated_action="stop_recovery"
        )
        
    # Rule 2: Cannot automate retries for permanent failures
    is_recoverable = diagnosis.get("is_recoverable", False)
    if action in ["immediate_retry", "delayed_retry"] and not is_recoverable:
        return PolicyDecision(
            allowed=False,
            reason="Cannot execute automated retries for non-recoverable failures.",
            mutated_action="request_new_payment_method"
        )
        
    # Rule 3: Enforce delays for NSF (transient_customer)
    category = diagnosis.get("failure_category", "")
    retry_timing = strategy_dict.get("retry_timing_hours", 0)
    if category == "transient_customer" and action == "immediate_retry":
        return PolicyDecision(
            allowed=False,
            reason="Immediate retries are prohibited for insufficient funds. Must use delayed retry.",
            mutated_action="delayed_retry"
        )

    # Rule 4: Idempotency / Loop prevention
    from app.db.state.db import get_session
    from app.db.state.models import RecoveryCase, RecoveryAttempt
    with get_session() as db:
        case = db.query(RecoveryCase).filter_by(payment_id=payment_id).first()
        if case:
            existing = db.query(RecoveryAttempt).filter_by(
                case_id=case.case_id,
                action_type=action,
                status="success"
            ).first()
            if existing and action not in ["immediate_retry", "delayed_retry"]:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Idempotency Guard: Action {action} was already successfully executed.",
                    mutated_action="stop_recovery"
                )

    return PolicyDecision(
        allowed=True,
        reason="Strategy passed all safety checks."
    )


def policy_node(state: RecoveryState) -> Dict[str, Any]:
    """
    LangGraph node for Policy Guard validation.
    """
    strategy = state.get("strategy", {})
    
    logger.info(
        "Policy node processing",
        extra={"payment_id": state.get("payment_id")}
    )

    decision = _evaluate_policy(strategy, state)

    content = f"Policy check passed: {decision.reason}" if decision.allowed else f"Policy check FAILED: {decision.reason}. Mutated action to: {decision.mutated_action}"
    
    # Save the decision to the DB AuditLog and RecoveryEvent
    from app.db.state.db import get_session
    from app.db.state.models import AuditLog, RecoveryCase, RecoveryEvent
    with get_session() as db:
        case = db.query(RecoveryCase).filter_by(payment_id=state.get("payment_id")).first()
        if case:
            audit = AuditLog(
                action="policy_decision",
                resource_type="recovery_case",
                resource_id=case.id,
                details={
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "original_action": strategy.get("action"),
                    "mutated_action": decision.mutated_action
                }
            )
            db.add(audit)
            
            event = RecoveryEvent(
                case_id=case.case_id,
                event_type="policy_decision",
                agent_name="policy_guard",
                event_data=decision.model_dump()
            )
            db.add(event)
            db.commit()

    # Create approved_strategy, leaving original untouched
    approved_strategy = strategy.copy()
    if not decision.allowed and decision.mutated_action:
        approved_strategy["action"] = decision.mutated_action
        approved_strategy["rationale"] = f"Mutated by Policy Guard: {decision.reason}"

    return {
        "policy_decision": decision.model_dump(),
        "strategy": strategy,  # Preserve the original proposed strategy
        "approved_strategy": approved_strategy,
        "messages": [{
            "role": "system",
            "content": content
        }]
    }
