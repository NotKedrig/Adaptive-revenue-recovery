"""
app/api/queue.py — Endpoints for the Revenue Recovery Operations Console.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.api.recovery_runner import (
    TERMINAL_STATUSES,
    can_advance,
    initial_state,
    run_cycle,
    serialize_state,
)
from app.db.state.db import get_session
from app.db.state.models import (
    Customer,
    Payment,
    RecoveryAttempt,
    RecoveryCase,
    RecoveryEvent,
)

router = APIRouter(prefix="/api", tags=["revenue_recovery"])


class MetricsResponse(BaseModel):
    revenue_at_risk: float
    revenue_recovered: float
    recovery_rate_percent: float
    as_of: str


class QueueItemResponse(BaseModel):
    case_id: str
    payment_id: str
    amount: float
    currency: str
    failure_type: str
    failure_reason: Optional[str] = None
    status: str
    customer_id: Optional[str] = None
    payment_method: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    latest_action: Optional[str] = None
    latest_outcome: Optional[str] = None
    next_action: Optional[str] = None
    next_action_delay_hours: Optional[int] = None
    simulated_time_hours: int = 0
    recovered_amount: Optional[float] = None
    can_advance: bool = True
    workflow_started: bool = False


class CaseDetailResponse(QueueItemResponse):
    pass


class TimelineEventResponse(BaseModel):
    id: int
    event_type: str
    timestamp: str
    actor: str
    status: str
    summary: str
    details: str
    metadata: dict = Field(default_factory=dict)


class AdvanceResponse(BaseModel):
    case_id: str
    status: str
    can_advance: bool
    simulated_time_hours: int
    attempt_count: int


class DemoPopulateResponse(BaseModel):
    status: str
    message: str
    case_ids: List[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _progress(case: RecoveryCase) -> dict[str, Any]:
    config = case.strategy_config if isinstance(case.strategy_config, dict) else {}
    return config if isinstance(config, dict) else {}


def _graph_state(case: RecoveryCase) -> dict[str, Any] | None:
    state = _progress(case).get("graph_state")
    return state if isinstance(state, dict) else None


def _event_data(event: RecoveryEvent) -> dict[str, Any]:
    data = event.event_data
    return data if isinstance(data, dict) else {}


def _latest_of_type(events: list[RecoveryEvent], event_type: str) -> RecoveryEvent | None:
    for event in reversed(events):
        if event.event_type == event_type:
            return event
    return None


def _derive_queue_fields(case: RecoveryCase) -> dict[str, Any]:
    payment = case.payment
    events = sorted(case.events or [], key=lambda item: (item.timestamp, item.id or 0))
    attempts = case.attempts or []
    progress = _progress(case)
    state = _graph_state(case)

    latest_action_event = _latest_of_type(events, "action_executed")
    latest_signal = _latest_of_type(events, "recovery_signal")
    latest_strategy = _latest_of_type(events, "strategy_proposed")
    latest_adaptive = _latest_of_type(events, "adaptive_transition")

    latest_action = None
    if latest_action_event:
        latest_action = _event_data(latest_action_event).get("action")

    latest_outcome = None
    if latest_signal:
        latest_outcome = _event_data(latest_signal).get("signal_type")

    next_action = None
    next_delay = None
    latest_event = events[-1] if events else None
    latest_type = latest_event.event_type if latest_event else None

    if latest_type in {"strategy_proposed", "policy_decision", "adaptive_transition"}:
        if latest_adaptive and (
            not latest_strategy
            or (latest_adaptive.timestamp, latest_adaptive.id or 0)
            >= (latest_strategy.timestamp, latest_strategy.id or 0)
        ):
            next_action = _event_data(latest_adaptive).get("new_strategy_action")
        elif latest_strategy:
            data = _event_data(latest_strategy)
            next_action = data.get("action")
            delay = data.get("retry_timing_hours")
            next_delay = int(delay) if delay is not None else None
        if next_delay is None and state:
            delay = (state.get("strategy") or {}).get("retry_timing_hours")
            if delay is not None:
                next_delay = int(delay)
    elif latest_strategy and latest_type in {None, "case_created", "intake_complete", "diagnosis"}:
        data = _event_data(latest_strategy)
        next_action = data.get("action")
        delay = data.get("retry_timing_hours")
        next_delay = int(delay) if delay is not None else None

    workflow_started = any(
        event.event_type not in {"case_created"} for event in events
    ) or bool(progress.get("workflow_started"))

    simulated_time = progress.get("simulated_time_hours")
    if simulated_time is None and state:
        simulated_time = state.get("simulated_time_hours", 0)

    attempt_count = len(attempts)
    if state and state.get("attempt_count") is not None:
        attempt_count = int(state.get("attempt_count") or attempt_count)

    max_attempts = 3
    if state and state.get("max_attempts") is not None:
        max_attempts = int(state.get("max_attempts") or 3)

    recovered_amount = float(payment.amount) if case.status == "recovered" else None
    advanceable = can_advance(state, case.status)

    return {
        "case_id": case.case_id,
        "payment_id": payment.payment_id if payment else "",
        "amount": float(payment.amount) if payment else 0.0,
        "currency": (payment.currency if payment else "INR") or "INR",
        "failure_type": (payment.failure_code if payment else None) or "unknown",
        "failure_reason": payment.failure_reason if payment else None,
        "status": case.status,
        "customer_id": payment.customer_id if payment else None,
        "payment_method": payment.payment_method if payment else None,
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
        "latest_action": latest_action,
        "latest_outcome": latest_outcome,
        "next_action": next_action,
        "next_action_delay_hours": next_delay,
        "simulated_time_hours": int(simulated_time or 0),
        "recovered_amount": recovered_amount,
        "can_advance": advanceable,
        "workflow_started": workflow_started,
    }


def _load_cases(db, recovered: bool) -> list[RecoveryCase]:
    query = (
        db.query(RecoveryCase)
        .options(
            joinedload(RecoveryCase.payment),
            joinedload(RecoveryCase.events),
            joinedload(RecoveryCase.attempts),
        )
        .join(Payment)
    )
    if recovered:
        query = query.filter(RecoveryCase.status == "recovered")
    else:
        query = query.filter(RecoveryCase.status != "recovered")
    return query.order_by(RecoveryCase.created_at.asc()).all()


def _timeline_status(event_type: str, data: dict[str, Any]) -> str:
    if event_type == "policy_decision":
        if data.get("allowed"):
            return "success"
        return "warning"
    if event_type == "recovery_signal":
        signal = data.get("signal_type", "")
        if signal == "success":
            return "success"
        if "fail" in str(signal) or signal == "permanent_failure":
            return "error"
        return "info"
    if event_type == "adaptive_transition":
        return "warning"
    if event_type in {"recovery_complete"} or data.get("simulated_outcome") == "recovery_successful":
        return "success"
    return "info"


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    with get_session() as db:
        at_risk_query = (
            db.query(func.sum(Payment.amount))
            .join(RecoveryCase)
            .filter(RecoveryCase.status != "recovered")
            .scalar()
        )
        recovered_query = (
            db.query(func.sum(Payment.amount))
            .join(RecoveryCase)
            .filter(RecoveryCase.status == "recovered")
            .scalar()
        )
        revenue_at_risk = float(at_risk_query) if at_risk_query else 0.0
        revenue_recovered = float(recovered_query) if recovered_query else 0.0
        eligible = revenue_at_risk + revenue_recovered
        rate = (revenue_recovered / eligible) * 100.0 if eligible > 0 else 0.0
        return MetricsResponse(
            revenue_at_risk=revenue_at_risk,
            revenue_recovered=revenue_recovered,
            recovery_rate_percent=round(rate, 1),
            as_of=_now_iso(),
        )


@router.get("/queue", response_model=List[QueueItemResponse])
def get_live_queue():
    with get_session() as db:
        return [QueueItemResponse(**_derive_queue_fields(case)) for case in _load_cases(db, recovered=False)]


@router.get("/recovered", response_model=List[QueueItemResponse])
def get_recovered_queue():
    with get_session() as db:
        return [QueueItemResponse(**_derive_queue_fields(case)) for case in _load_cases(db, recovered=True)]


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: str):
    with get_session() as db:
        case = (
            db.query(RecoveryCase)
            .options(
                joinedload(RecoveryCase.payment),
                joinedload(RecoveryCase.events),
                joinedload(RecoveryCase.attempts),
            )
            .filter(RecoveryCase.case_id == case_id)
            .first()
        )
        if not case:
            raise HTTPException(status_code=404, detail="Recovery case not found.")
        return CaseDetailResponse(**_derive_queue_fields(case))


@router.get("/cases/{case_id}/timeline", response_model=List[TimelineEventResponse])
def get_case_timeline(case_id: str):
    with get_session() as db:
        case = db.query(RecoveryCase).filter(RecoveryCase.case_id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Recovery case not found.")
        events = (
            db.query(RecoveryEvent)
            .filter(RecoveryEvent.case_id == case_id)
            .order_by(RecoveryEvent.timestamp.asc(), RecoveryEvent.id.asc())
            .all()
        )
        timeline: list[TimelineEventResponse] = []
        for event in events:
            data = _event_data(event)
            timeline.append(
                TimelineEventResponse(
                    id=event.id,
                    event_type=event.event_type,
                    timestamp=event.timestamp.isoformat() if event.timestamp else _now_iso(),
                    actor=event.agent_name,
                    status=_timeline_status(event.event_type, data),
                    summary=event.event_type.replace("_", " "),
                    details="",
                    metadata=data,
                )
            )
        return timeline


@router.post("/cases/{case_id}/advance", response_model=AdvanceResponse)
def advance_recovery(case_id: str):
    """Run the next cycle of the existing recovery workflow for this case."""
    with get_session() as db:
        case = (
            db.query(RecoveryCase)
            .options(joinedload(RecoveryCase.payment))
            .filter(RecoveryCase.case_id == case_id)
            .first()
        )
        if not case:
            raise HTTPException(status_code=404, detail="Recovery case not found.")
        if case.status in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="This case is already complete and cannot be advanced.",
            )
        payment = case.payment
        payment_id = payment.payment_id
        failure_code = payment.failure_code or ""
        failure_reason = payment.failure_reason or ""
        stored = deepcopy(_graph_state(case)) if _graph_state(case) else None
        case_status = case.status

    first_cycle = stored is None
    if first_cycle:
        state = initial_state(
            payment_id,
            failure_code,
            failure_reason,
        )
    else:
        state = dict(stored)

    if not can_advance(state if not first_cycle else None, case_status if not first_cycle else "open"):
        raise HTTPException(
            status_code=409,
            detail="This case is already complete and cannot be advanced.",
        )

    new_state = run_cycle(state, first_cycle=first_cycle)

    with get_session() as db:
        case = db.query(RecoveryCase).filter(RecoveryCase.case_id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Recovery case not found.")
        progress = dict(_progress(case))
        progress["graph_state"] = serialize_state(new_state)
        progress["workflow_started"] = True
        progress["simulated_time_hours"] = int(new_state.get("simulated_time_hours") or 0)
        case.strategy_config = progress
        flag_modified(case, "strategy_config")
        db.add(case)
        db.commit()
        db.refresh(case)
        status = case.status
        attempt_count = int(new_state.get("attempt_count") or 0)
        simulated = int(new_state.get("simulated_time_hours") or 0)
        advanceable = can_advance(new_state, status)

    return AdvanceResponse(
        case_id=case_id,
        status=status,
        can_advance=advanceable,
        simulated_time_hours=simulated,
        attempt_count=attempt_count,
    )


@router.post("/demo/populate", response_model=DemoPopulateResponse)
def populate_demo_data():
    """Load three deterministic unpaid recovery cases. Does not run the workflow."""
    from app.simulation.engine import SimulationEngine
    from app.simulation.interfaces import SimulatedPaymentEvent

    with get_session() as db:
        db.query(RecoveryEvent).delete()
        db.query(RecoveryAttempt).delete()
        db.query(RecoveryCase).delete()
        db.query(Payment).delete()
        db.query(Customer).delete()
        db.commit()

    engine = SimulationEngine(seed=42)
    events = [
        SimulatedPaymentEvent(
            payment_id="pay_nsf_002",
            merchant_id="merchant_001",
            customer_id="customer_nsf_002",
            amount=8200.0,
            currency="INR",
            payment_method="card",
            failure_code="insufficient_funds",
            failure_reason="Insufficient funds",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        SimulatedPaymentEvent(
            payment_id="pay_tech_001",
            merchant_id="merchant_001",
            customer_id="customer_tech_001",
            amount=4500.0,
            currency="INR",
            payment_method="card",
            failure_code="bank_timeout",
            failure_reason="Bank timeout",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        SimulatedPaymentEvent(
            payment_id="pay_perm_003",
            merchant_id="merchant_001",
            customer_id="customer_perm_003",
            amount=999.0,
            currency="INR",
            payment_method="card",
            failure_code="invalid_card",
            failure_reason="Invalid card",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
    ]

    case_ids = [engine.load_payment_event(event) for event in events]
    return DemoPopulateResponse(
        status="success",
        message="Demo data loaded. 3 recovery scenarios ready.",
        case_ids=case_ids,
    )
