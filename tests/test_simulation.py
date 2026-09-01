"""
tests/test_simulation.py — Tests for the simulation engine.
"""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.state.models import Base, Customer, Payment, RecoveryCase, RecoveryAttempt, RecoveryEvent
from app.simulation.interfaces import SimulatedPaymentEvent, RecoveryActionRequest
from app.simulation.engine import SimulationEngine
from app.simulation.dataset import generate_dataset


@pytest.fixture(scope="module")
def db_url(tmp_path_factory):
    """Create a temporary SQLite database for simulation tests."""
    tmp = tmp_path_factory.mktemp("sim_db")
    url = f"sqlite:///{tmp / 'test_sim.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return url


def test_load_payment_event_creates_records(db_url):
    engine = SimulationEngine(seed=42)
    events = generate_dataset(n=1, seed=42)
    event = events[0]

    case_id = engine.load_payment_event(event, database_url=db_url)

    assert case_id == f"case_{event.payment_id}"

    # Verify database records
    from sqlalchemy import create_engine as ce
    from sqlalchemy.orm import sessionmaker as sm
    eng = ce(db_url, connect_args={"check_same_thread": False})
    Session = sm(bind=eng)
    session = Session()

    customer = session.query(Customer).filter_by(customer_id=event.customer_id).first()
    assert customer is not None

    payment = session.query(Payment).filter_by(payment_id=event.payment_id).first()
    assert payment is not None
    assert float(payment.amount) == pytest.approx(event.amount, abs=0.01)

    case = session.query(RecoveryCase).filter_by(case_id=case_id).first()
    assert case is not None
    assert case.status == "open"

    # Verify event log
    events_db = session.query(RecoveryEvent).filter_by(case_id=case_id).all()
    assert len(events_db) >= 1
    assert events_db[0].event_type == "case_created"

    session.close()


def test_deterministic_simulation(db_url):
    """Two engines with the same seed produce identical outcomes."""
    engine_a = SimulationEngine(seed=99)
    engine_b = SimulationEngine(seed=99)

    # Generate outcomes for the same failure type
    outcome_a = engine_a.generate_payment_outcome(
        case_id="test_case_1", failure_code="bank_timeout",
        action_type="retry", amount=1000.0
    )
    outcome_b = engine_b.generate_payment_outcome(
        case_id="test_case_1", failure_code="bank_timeout",
        action_type="retry", amount=1000.0
    )

    assert outcome_a.status == outcome_b.status
    assert outcome_a.amount_recovered == outcome_b.amount_recovered


def test_execute_recovery_action(db_url):
    """Test that executing an action creates a RecoveryAttempt record."""
    engine = SimulationEngine(seed=42)

    # First load a payment event
    events = generate_dataset(n=1, seed=100)
    event = events[0]
    case_id = engine.load_payment_event(event, database_url=db_url)

    # Execute a recovery action
    request = RecoveryActionRequest(
        case_id=case_id,
        action_type="retry",
        payload={"delay_seconds": 0},
    )
    response = engine.execute_recovery_action(request, event.failure_code, database_url=db_url)

    assert isinstance(response.success, bool)
    assert response.provider_id is not None

    # Verify attempt record
    from sqlalchemy import create_engine as ce
    from sqlalchemy.orm import sessionmaker as sm
    eng = ce(db_url, connect_args={"check_same_thread": False})
    Session = sm(bind=eng)
    session = Session()

    attempt = session.query(RecoveryAttempt).filter_by(case_id=case_id).first()
    assert attempt is not None
    assert attempt.action_type == "retry"
    session.close()


def test_customer_response_generation():
    engine = SimulationEngine(seed=42)
    response = engine.generate_customer_response(
        case_id="case_test",
        customer_id="cust_test",
        action_type="notify_sms",
    )
    assert response.response_type in ["clicked_link", "ignored", "replied_stop"]
    assert response.case_id == "case_test"


def test_non_recoverable_failure_outcomes():
    """Invalid card retries should almost always fail."""
    engine = SimulationEngine(seed=42)
    results = []
    for i in range(20):
        outcome = engine.generate_payment_outcome(
            case_id=f"case_{i}",
            failure_code="invalid_card",
            action_type="retry",
            amount=500.0,
        )
        results.append(outcome.status)

    # With 0% retry probability for invalid_card, almost all should fail
    success_count = results.count("success")
    assert success_count <= 5  # At most a few might be "partial"
