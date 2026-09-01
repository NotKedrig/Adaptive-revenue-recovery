"""
tests/test_phase3.py — Tests for Recovery Strategy, Policy Guard, and Action Execution.
"""
import pytest
from app.graph.state import RecoveryState
from app.agents.strategy import strategy_node
from app.agents.policy import policy_node
from app.agents.action import action_node
from app.agents.schemas import RecoveryActionRequest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.state.models import Base, Customer, Payment, RecoveryCase, RecoveryAttempt, AuditLog

@pytest.fixture(scope="function")
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'test_phase3.db'}"
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

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    session = Session()

    c1 = Customer(customer_id="c1", merchant_id="m1")
    p1 = Payment(payment_id="p1", customer_id="c1", amount=100.0, currency="INR", payment_method="card")
    case1 = RecoveryCase(case_id="case1", payment_id="p1", status="open", escalation_level="none")

    session.add_all([c1, p1, case1])
    session.commit()
    session.close()

    yield db_url

    db_module._engine = None
    db_module._SessionLocal = None


# --- Strategy Tests ---

def test_strategy_transient_technical_first_attempt():
    state = {"diagnosis": {"failure_category": "transient_technical", "is_recoverable": True}, "attempt_count": 0}
    res = strategy_node(state)
    strat = res["strategy"]
    assert strat["action"] == "immediate_retry"
    assert strat["retry_timing_hours"] == 0

def test_strategy_transient_technical_second_attempt():
    state = {"diagnosis": {"failure_category": "transient_technical", "is_recoverable": True}, "attempt_count": 1}
    res = strategy_node(state)
    strat = res["strategy"]
    assert strat["action"] == "delayed_retry"
    assert strat["retry_timing_hours"] == 4

def test_strategy_transient_customer_nsf():
    state = {"diagnosis": {"failure_category": "transient_customer", "is_recoverable": True}, "attempt_count": 0}
    res = strategy_node(state)
    strat = res["strategy"]
    assert strat["action"] == "delayed_retry"
    assert strat["channel"] == "sms"
    assert strat["retry_timing_hours"] == 48

def test_strategy_non_recoverable():
    state = {"diagnosis": {"failure_category": "permanent_card", "is_recoverable": False}, "attempt_count": 0}
    res = strategy_node(state)
    strat = res["strategy"]
    assert strat["action"] == "request_new_payment_method"
    assert strat["expected_outcome"] == "customer_update_required"


# --- Policy Guard Tests ---

def test_policy_allows_valid_strategy(seed_db):
    state = {
        "payment_id": "p1",
        "attempt_count": 0,
        "diagnosis": {"is_recoverable": True, "failure_category": "transient_technical"},
        "strategy": {"action": "immediate_retry", "maximum_attempts": 3}
    }
    res = policy_node(state)
    assert res["policy_decision"]["allowed"] is True
    assert res["strategy"]["action"] == "immediate_retry"

def test_policy_blocks_max_attempts(seed_db):
    state = {
        "payment_id": "p1",
        "attempt_count": 3,
        "diagnosis": {"is_recoverable": True},
        "strategy": {"action": "immediate_retry", "maximum_attempts": 3}
    }
    res = policy_node(state)
    assert res["policy_decision"]["allowed"] is False
    assert res["policy_decision"]["mutated_action"] == "stop_recovery"
    assert res["strategy"]["action"] == "immediate_retry"  # Original strategy is preserved
    assert res["approved_strategy"]["action"] == "stop_recovery"  # Strategy mutated

def test_policy_blocks_immediate_retry_for_nsf(seed_db):
    state = {
        "payment_id": "p1",
        "attempt_count": 0,
        "diagnosis": {"is_recoverable": True, "failure_category": "transient_customer"},
        "strategy": {"action": "immediate_retry", "retry_timing_hours": 0}
    }
    res = policy_node(state)
    assert res["policy_decision"]["allowed"] is False
    assert res["policy_decision"]["mutated_action"] == "delayed_retry"
    assert res["strategy"]["action"] == "immediate_retry"
    assert res["approved_strategy"]["action"] == "delayed_retry"

def test_policy_blocks_retry_on_non_recoverable(seed_db):
    state = {
        "payment_id": "p1",
        "attempt_count": 0,
        "diagnosis": {"is_recoverable": False},
        "strategy": {"action": "immediate_retry"}
    }
    res = policy_node(state)
    assert res["policy_decision"]["allowed"] is False
    assert res["policy_decision"]["mutated_action"] == "request_new_payment_method"
    assert res["strategy"]["action"] == "immediate_retry"
    assert res["approved_strategy"]["action"] == "request_new_payment_method"


# --- Action Execution Tests ---

def test_action_execution_and_persistence(seed_db):
    state = {
        "payment_id": "p1",
        "attempt_count": 0,
        "strategy": {"action": "payment_method_update_request", "channel": "email"}
    }
    res = action_node(state)
    
    # Check returns
    assert res["action_request"]["action_type"] == "payment_method_update_request"
    assert res["action_result"]["success"] is True
    assert res["attempt_count"] == 1
    
    # Check DB persistence
    engine = create_engine(seed_db, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    session = Session()
    attempts = session.query(RecoveryAttempt).all()
    assert len(attempts) == 1
    assert attempts[0].action_type == "payment_method_update_request"
    assert attempts[0].status == "success"
    session.close()


# --- Workflow Graph Test ---

def test_full_workflow_traversal_phase3(seed_db):
    from app.graph.workflow import build_graph
    graph = build_graph()
    
    # We pass intake manually or run from intake
    initial_state = {
        "payment_id": "p1",
        "failure_code": "bank_timeout",
        "failure_reason": "Bank timeout",
        "attempt_count": 0
    }
    
    config = {"configurable": {"thread_id": "test_phase3"}}
    final_state = graph.invoke(initial_state, config=config)
    
    # It should have traversed intake -> diagnosis -> strategy -> policy -> action
    assert "diagnosis" in final_state
    assert "strategy" in final_state
    assert "policy_decision" in final_state
    assert "action_result" in final_state
    
    assert final_state["policy_decision"]["allowed"] is True
    assert final_state["strategy"]["action"] == "immediate_retry"
    assert final_state["attempt_count"] == 1
    assert final_state["case_status"] in ["recovery_successful", "recovery_failed"] # Random outcome
