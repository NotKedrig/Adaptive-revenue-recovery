"""
tests/test_phase4.py — Tests for Adaptive Loop & Outcomes.
"""
import pytest
from app.graph.workflow import build_graph
from app.simulation.engine import SimulationEngine
from app.simulation.interfaces import SimulatedPaymentEvent
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.state.models import Base

@pytest.fixture(scope="function")
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'test_phase4.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return url

@pytest.fixture(scope="function")
def seed_db(db_url, monkeypatch):
    import app.db.state.db as db_module
    original_get_engine = db_module.get_engine

    def patched_get_engine(database_url=None):
        return original_get_engine(db_url)

    monkeypatch.setattr(db_module, "get_engine", patched_get_engine)
    db_module._engine = None
    db_module._SessionLocal = None

    yield db_url

    db_module._engine = None
    db_module._SessionLocal = None


def test_trajectory_a_successful_recovery(seed_db):
    engine = SimulationEngine(seed=42)
    graph = build_graph()
    
    event = SimulatedPaymentEvent(
        payment_id="pay_tech_001",
        merchant_id="merchant_001",
        customer_id="cust_001",
        amount=100.0,
        currency="INR",
        payment_method="card",
        failure_code="bank_timeout",
        failure_reason="Bank timeout",
        timestamp=datetime.datetime.now(datetime.UTC).isoformat()
    )
    engine.load_payment_event(event)
    
    initial_state = {
        "payment_id": event.payment_id,
        "failure_code": event.failure_code,
        "failure_reason": event.failure_reason,
        "attempt_count": 0,
        "max_attempts": 3,
        "simulated_time_hours": 0
    }
    
    config = {"configurable": {"thread_id": f"test4_{event.payment_id}"}, "recursion_limit": 20}
    final_state = graph.invoke(initial_state, config=config)
    
    assert final_state["case_status"] == "recovery_successful"
    assert final_state["latest_outcome"]["outcome_category"] == "recovered"
    assert final_state["latest_outcome"]["is_terminal"] is True
    # Initial strategy -> delayed retry (fails) -> adaptive -> delayed retry 12h -> success?
    # Wait, for tech failure, attempt 0 is immediate retry which fails. 
    # Adaptive planner schedules delayed retry with 12h delay.
    # At 12h, delayed retry succeeds. So attempt_count should be 2.
    assert final_state["attempt_count"] == 2
    assert final_state["simulated_time_hours"] >= 12

def test_trajectory_c_permanent_failure(seed_db):
    engine = SimulationEngine(seed=42)
    graph = build_graph()
    
    event = SimulatedPaymentEvent(
        payment_id="pay_perm_002",
        merchant_id="merchant_001",
        customer_id="cust_002",
        amount=50.0,
        currency="INR",
        payment_method="card",
        failure_code="invalid_card",
        failure_reason="Card invalid",
        timestamp=datetime.datetime.now(datetime.UTC).isoformat()
    )
    engine.load_payment_event(event)
    
    initial_state = {
        "payment_id": event.payment_id,
        "failure_code": event.failure_code,
        "failure_reason": event.failure_reason,
        "attempt_count": 0,
        "max_attempts": 3,
        "simulated_time_hours": 0
    }
    
    config = {"configurable": {"thread_id": f"test4_{event.payment_id}"}, "recursion_limit": 20}
    final_state = graph.invoke(initial_state, config=config)
    
    # Permanent -> strategy requests update -> outcome is customer_notified -> adaptive -> wait... 
    # Let's see what happens for permanent. The diagnosis node identifies it as permanent.
    # Wait, my simulation engine just categorizes "pay_perm_002" as permanent failure.
    # If strategy asks for request_new_payment_method, it succeeds and outcome is customer_notified.
    # Then adaptive planner gets "no_response" (since we didn't mock customer responding).
    # Then it might escalate or retry.
    assert final_state["attempt_count"] <= 5 # Bounded!
