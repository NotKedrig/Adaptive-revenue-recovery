"""
app/agents/action.py — Action Execution node.
"""
from typing import Any, Dict
from app.graph.state import RecoveryState
from app.agents.schemas import RecoveryActionRequest, RecoveryActionResult
from app.simulation.engine import SimulationEngine
import logging
import uuid
import datetime

logger = logging.getLogger(__name__)


def action_node(state: RecoveryState) -> Dict[str, Any]:
    """
    LangGraph node for Action Execution.
    Constructs the request and routes it to the Simulation Engine.
    """
    payment_id = state.get("payment_id")
    # Execute the strategy approved/mutated by the Policy Guard
    strategy = state.get("approved_strategy") or state.get("strategy", {})
    
    # 1. Build Action Request
    action_type = strategy.get("action", "unknown_action")
    request = RecoveryActionRequest(
        payment_id=payment_id,
        action_type=action_type,
        channel=strategy.get("channel"),
        delay_hours=strategy.get("retry_timing_hours", 0),
        idempotency_key=f"{payment_id}_{action_type}_{state.get('attempt_count', 0)}"
    )

    logger.info(
        "Action node executing",
        extra={"payment_id": payment_id, "action": action_type}
    )

    # 2. Persist RecoveryAttempt to DB
    from app.db.state.db import get_session
    from app.db.state.models import RecoveryCase, RecoveryAttempt
    with get_session() as db:
        case = db.query(RecoveryCase).filter_by(payment_id=payment_id).first()
        if case:
            attempt = RecoveryAttempt(
                case_id=case.case_id,
                action_type=action_type,
                channel=request.channel,
                status="pending"
            )
            db.add(attempt)
            db.flush()
            attempt_id = attempt.id
            db.commit()
        else:
            attempt_id = None

    # 3. Execute via Simulation Engine
    # Note: In a production app this would call real external providers.
    engine = SimulationEngine()
    result = engine.execute_action(request)

    # 4. Update RecoveryAttempt result
    if attempt_id:
        with get_session() as db:
            attempt = db.query(RecoveryAttempt).get(attempt_id)
            if attempt:
                attempt.status = "success" if result.success else "failed"
                attempt.response_payload = result.model_dump()
                db.commit()

    return {
        "action_request": request.model_dump(),
        "action_result": result.model_dump(),
        "attempt_count": state.get("attempt_count", 0) + 1,
        "case_status": result.simulated_outcome,
        "messages": [{
            "role": "system",
            "content": f"Action Executed: {action_type}. Outcome: {result.simulated_outcome}. Success: {result.success}"
        }]
    }
