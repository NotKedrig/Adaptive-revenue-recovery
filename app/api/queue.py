"""
app/api/queue.py — Endpoints for the Phase 5 Revenue Recovery Frontend.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Any
from sqlalchemy import func

from app.db.state.db import get_session
from app.db.state.models import RecoveryCase, Payment, RecoveryEvent

router = APIRouter(prefix="/api", tags=["revenue_recovery"])


# --- Schemas ---

class MetricsResponse(BaseModel):
    revenue_at_risk: float
    revenue_recovered: float
    recovery_rate_percent: float


class QueueItemResponse(BaseModel):
    case_id: str
    payment_id: str
    amount: float
    currency: str
    failure_type: str
    status: str
    latest_action: Optional[str] = None
    latest_outcome: Optional[str] = None


class EventMetadata(BaseModel):
    status: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    metadata: dict = {}


class TimelineEventResponse(BaseModel):
    event_type: str
    timestamp: str
    actor: str
    status: str
    summary: str
    details: str
    metadata: dict


# --- Endpoints ---

@router.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    with get_session() as db:
        # Revenue at Risk (cases not recovered)
        at_risk_query = db.query(func.sum(Payment.amount)).join(RecoveryCase).filter(
            RecoveryCase.status != "recovered"
        ).scalar()
        revenue_at_risk = float(at_risk_query) if at_risk_query else 0.0
        
        # Revenue Recovered
        recovered_query = db.query(func.sum(Payment.amount)).join(RecoveryCase).filter(
            RecoveryCase.status == "recovered"
        ).scalar()
        revenue_recovered = float(recovered_query) if recovered_query else 0.0
        
        # Recovery Rate (by case count)
        total_cases = db.query(RecoveryCase).count()
        recovered_cases = db.query(RecoveryCase).filter(RecoveryCase.status == "recovered").count()
        
        rate = 0.0
        if total_cases > 0:
            rate = (recovered_cases / total_cases) * 100.0
            
        return MetricsResponse(
            revenue_at_risk=revenue_at_risk,
            revenue_recovered=revenue_recovered,
            recovery_rate_percent=round(rate, 2)
        )


@router.get("/queue", response_model=List[QueueItemResponse])
def get_live_queue():
    """Returns cases that are open/active."""
    with get_session() as db:
        cases = db.query(RecoveryCase).join(Payment).filter(
            RecoveryCase.status == "open"
        ).all()
        
        results = []
        for c in cases:
            results.append(QueueItemResponse(
                case_id=c.case_id,
                payment_id=c.payment.payment_id,
                amount=float(c.payment.amount),
                currency=c.payment.currency,
                failure_type=c.payment.failure_code or "unknown",
                status=c.status,
                latest_action="Processing",
                latest_outcome="Pending"
            ))
        return results


@router.get("/recovered", response_model=List[QueueItemResponse])
def get_recovered_queue():
    """Returns ONLY successfully recovered cases."""
    with get_session() as db:
        cases = db.query(RecoveryCase).join(Payment).filter(
            RecoveryCase.status == "recovered"
        ).all()
        
        results = []
        for c in cases:
            results.append(QueueItemResponse(
                case_id=c.case_id,
                payment_id=c.payment.payment_id,
                amount=float(c.payment.amount),
                currency=c.payment.currency,
                failure_type=c.payment.failure_code or "unknown",
                status=c.status,
                latest_action="Recovered",
                latest_outcome="Success"
            ))
        return results


@router.get("/cases/{case_id}/timeline", response_model=List[TimelineEventResponse])
def get_case_timeline(case_id: str):
    """Returns a structured timeline for a given case."""
    with get_session() as db:
        events = db.query(RecoveryEvent).filter(RecoveryEvent.case_id == case_id).order_by(RecoveryEvent.timestamp).all()
        
        timeline = []
        for e in events:
            data = e.event_data or {}
            
            # Map raw event data to UI friendly fields
            summary = ""
            details = ""
            status = "info"
            
            if e.event_type == "diagnosis":
                summary = f"Diagnosed: {data.get('failure_category', 'unknown')}"
                details = data.get('reasoning', '')
            elif e.event_type == "strategy_proposed":
                summary = f"Proposed Strategy: {data.get('action')}"
                details = data.get('rationale', '')
            elif e.event_type == "policy_decision":
                allowed = data.get('allowed')
                if allowed:
                    summary = "Strategy Approved"
                    status = "success"
                else:
                    summary = f"Strategy Modified: {data.get('mutated_action')}"
                    status = "warning"
                details = data.get('reason', '')
            elif e.event_type == "action_executed" or e.event_type == "recovery_signal":
                # For Phase 4 we use recovery_signal primarily
                sig_type = data.get('signal_type', '')
                summary = f"Signal Detected: {sig_type}"
                details = str(data.get('context', ''))
                if sig_type == "success":
                    status = "success"
                elif "fail" in sig_type:
                    status = "error"
            else:
                summary = str(e.event_type)
                
            timeline.append(TimelineEventResponse(
                event_type=e.event_type,
                timestamp=e.timestamp.isoformat(),
                actor=e.agent_name,
                status=status,
                summary=summary,
                details=details,
                metadata=data
            ))
            
        return timeline


@router.post("/demo/populate")
def populate_demo_data():
    """Deterministically populates the SQLite database with 3 trajectories."""
    from app.simulation.dataset import generate_dataset
    from app.simulation.engine import SimulationEngine
    from app.graph.workflow import build_graph
    from app.simulation.interfaces import SimulatedPaymentEvent
    import datetime
    
    # 1. Clean DB
    with get_session() as db:
        db.query(RecoveryEvent).delete()
        db.query(RecoveryCase).delete()
        db.query(Payment).delete()
        from app.db.state.models import Customer
        db.query(Customer).delete()
        db.commit()

    engine = SimulationEngine(seed=42)
    graph = build_graph()
    
    events = [
        SimulatedPaymentEvent(
            payment_id="pay_tech_001", merchant_id="merchant_001", customer_id="cust_001",
            amount=100.0, currency="INR", payment_method="card",
            failure_code="bank_timeout", failure_reason="Bank timeout",
            timestamp=datetime.datetime.now(datetime.UTC).isoformat()
        ),
        SimulatedPaymentEvent(
            payment_id="pay_nsf_002", merchant_id="merchant_001", customer_id="cust_002",
            amount=50.0, currency="USD", payment_method="card",
            failure_code="insufficient_funds", failure_reason="Insufficient funds",
            timestamp=datetime.datetime.now(datetime.UTC).isoformat()
        ),
        SimulatedPaymentEvent(
            payment_id="pay_perm_003", merchant_id="merchant_001", customer_id="cust_003",
            amount=999.0, currency="EUR", payment_method="card",
            failure_code="invalid_card", failure_reason="Card expired",
            timestamp=datetime.datetime.now(datetime.UTC).isoformat()
        )
    ]

    for event in events:
        engine.load_payment_event(event)
        
        initial_state = {
            "payment_id": event.payment_id,
            "failure_code": event.failure_code,
            "failure_reason": event.failure_reason,
            "attempt_count": 0,
            "max_attempts": 3,
            "simulated_time_hours": 0
        }
        config = {"configurable": {"thread_id": f"demo5_{event.payment_id}"}, "recursion_limit": 20}
        graph.invoke(initial_state, config=config)

    return {"status": "success", "message": "Demo data populated deterministically."}
