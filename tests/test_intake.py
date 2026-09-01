"""
tests/test_intake.py — Tests for the Intake Node.
"""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.state.models import Base, Customer, Payment, RecoveryCase, AuditLog, RecoveryEvent
from app.agents.intake import intake_node


@pytest.fixture(scope="module")
def db_url(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("intake_db")
    url = f"sqlite:///{tmp / 'test_intake.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    # Seed test data
    Session = sessionmaker(bind=engine)
    session = Session()
    customer = Customer(customer_id="cust_intake_001", merchant_id="merch_test")
    payment = Payment(
        payment_id="pay_intake_001",
        customer_id="cust_intake_001",
        amount=Decimal("2500.00"),
        currency="INR",
        payment_method="card",
        card_network="Visa",
        issuer_bank="HDFC Bank",
        failure_code="bank_timeout",
        failure_reason="Bank did not respond within timeout",
    )
    session.add_all([customer, payment])
    session.commit()
    session.close()
    return url


def test_intake_populates_state(db_url, monkeypatch):
    """Intake should populate the full RecoveryState from DB records."""
    # Monkey-patch get_session to use our test DB
    import app.db.state.db as db_module
    original_get_engine = db_module.get_engine

    def patched_get_engine(database_url=None):
        return original_get_engine(db_url)

    monkeypatch.setattr(db_module, "get_engine", patched_get_engine)
    # Reset cached engine
    db_module._engine = None
    db_module._SessionLocal = None

    state = {
        "payment_id": "pay_intake_001",
        "failure_code": "bank_timeout",
        "failure_reason": "Bank did not respond within timeout",
        "messages": [],
        "runtime_metadata": [],
    }

    result = intake_node(state)

    assert result["payment_id"] == "pay_intake_001"
    assert result["customer_id"] == "cust_intake_001"
    assert result["amount"] == 2500.0
    assert result["failure_code"] == "bank_timeout"
    assert result["case_status"] == "intake_complete"
    assert result["attempt_count"] == 0

    # Reset
    db_module._engine = None
    db_module._SessionLocal = None


def test_intake_missing_payment(db_url, monkeypatch):
    """Intake should return error status for non-existent payment."""
    import app.db.state.db as db_module
    original_get_engine = db_module.get_engine

    def patched_get_engine(database_url=None):
        return original_get_engine(db_url)

    monkeypatch.setattr(db_module, "get_engine", patched_get_engine)
    db_module._engine = None
    db_module._SessionLocal = None

    state = {
        "payment_id": "pay_nonexistent",
        "failure_code": "unknown",
        "failure_reason": "",
        "messages": [],
        "runtime_metadata": [],
    }

    result = intake_node(state)
    assert result["case_status"] == "error"

    db_module._engine = None
    db_module._SessionLocal = None


def test_intake_creates_audit_log(db_url, monkeypatch):
    """Intake should create an AuditLog entry."""
    import app.db.state.db as db_module
    original_get_engine = db_module.get_engine

    def patched_get_engine(database_url=None):
        return original_get_engine(db_url)

    monkeypatch.setattr(db_module, "get_engine", patched_get_engine)
    db_module._engine = None
    db_module._SessionLocal = None

    state = {
        "payment_id": "pay_intake_001",
        "failure_code": "bank_timeout",
        "failure_reason": "Bank did not respond within timeout",
        "messages": [],
        "runtime_metadata": [],
    }

    intake_node(state)

    # Check audit log
    eng = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=eng)
    session = Session()
    audits = session.query(AuditLog).filter_by(action="intake_processed").all()
    assert len(audits) >= 1
    session.close()

    db_module._engine = None
    db_module._SessionLocal = None


def test_intake_no_payment_id():
    """Intake should handle missing payment_id gracefully."""
    state = {"messages": [], "runtime_metadata": []}
    result = intake_node(state)
    assert result["case_status"] == "error"
