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
    engine = SimulationEngine()
    current_time = state.get("simulated_time_hours", 0)
    result, new_time = engine.execute_action(request, current_time)

    # 4. Update RecoveryAttempt result and log RecoveryEvent
    if attempt_id:
        with get_session() as db:
            attempt = db.query(RecoveryAttempt).get(attempt_id)
            if attempt:
                attempt.status = "success" if result.success else "failed"
                attempt.response_payload = result.model_dump()
                
                event = RecoveryEvent(
                    case_id=attempt.case_id,
                    event_type="action_executed",
                    agent_name="action_executor",
                    event_data={
                        "action": action_type,
                        "result": result.model_dump()
                    }
                )
                db.add(event)
                
                db.commit()

    # Phase 4: History Accumulation
    action_history = list(state.get("action_history") or [])
    action_history.append(request.model_dump())
    
    strategy_history = list(state.get("strategy_history") or [])
    if strategy:
        strategy_history.append(strategy)

    return {
        "action_request": request.model_dump(),
        "action_result": result.model_dump(),
        "attempt_count": state.get("attempt_count", 0) + 1,
        "case_status": result.simulated_outcome,
        "simulated_time_hours": new_time,
        "action_history": action_history,
        "strategy_history": strategy_history,
        "messages": [{
            "role": "system",
            "content": f"Action Executed: {action_type} at T+{new_time}h. Outcome: {result.simulated_outcome}. Success: {result.success}"
        }]
    }
