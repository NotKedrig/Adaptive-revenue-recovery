"""
tests/test_api_queue.py — Frontend contract tests for metrics, demo data, and recovery stepping.
"""
import pytest

from app.db.state.models import Base


@pytest.fixture(scope="function")
def db_url(tmp_path):
    from sqlalchemy import create_engine

    url = f"sqlite:///{tmp_path / 'test_api_queue.db'}"
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


def test_metrics_use_monetary_recovery_rate(seed_db):
    from app.db.state.db import get_session
    from app.db.state.models import Customer, Payment, RecoveryCase
    from app.api.queue import get_metrics

    with get_session() as db:
        db.add(Customer(customer_id="c1", merchant_id="m1"))
        db.add(Customer(customer_id="c2", merchant_id="m1"))
        db.add(Payment(payment_id="p1", customer_id="c1", amount=8200, currency="INR"))
        db.add(Payment(payment_id="p2", customer_id="c2", amount=4500, currency="INR"))
        db.add(RecoveryCase(case_id="case_p1", payment_id="p1", status="open"))
        db.add(RecoveryCase(case_id="case_p2", payment_id="p2", status="recovered"))
        db.commit()

    metrics = get_metrics()
    assert metrics.revenue_at_risk == 8200.0
    assert metrics.revenue_recovered == 4500.0
    assert metrics.recovery_rate_percent == 35.4


def test_demo_populate_creates_inr_cases_without_running_workflow(seed_db):
    from app.api.queue import get_live_queue, get_metrics, get_recovered_queue, populate_demo_data

    result = populate_demo_data()
    assert result.status == "success"
    assert len(result.case_ids) == 3

    live = get_live_queue()
    recovered = get_recovered_queue()
    metrics = get_metrics()

    assert recovered == []
    assert {item.payment_id for item in live} == {"pay_tech_001", "pay_nsf_002", "pay_perm_003"}
    assert all(item.currency == "INR" for item in live)
    assert {item.amount for item in live} == {4500.0, 8200.0, 999.0}
    assert all(item.status == "open" for item in live)
    assert all(item.can_advance for item in live)
    assert all(not item.workflow_started for item in live)
    assert metrics.revenue_at_risk == 13699.0
    assert metrics.revenue_recovered == 0.0
    assert metrics.recovery_rate_percent == 0.0


def test_advance_tech_case_adapts_then_recovers(seed_db):
    from app.api.queue import (
        advance_recovery,
        get_case,
        get_case_timeline,
        get_metrics,
        get_recovered_queue,
        populate_demo_data,
    )

    populate_demo_data()
    case_id = "case_pay_tech_001"

    first = advance_recovery(case_id)
    assert first.status != "recovered"
    assert first.can_advance is True

    timeline = get_case_timeline(case_id)
    types = [event.event_type for event in timeline]
    assert "diagnosis" in types
    assert "strategy_proposed" in types
    assert "policy_decision" in types
    assert "action_executed" in types
    assert "recovery_signal" in types
    assert "adaptive_transition" not in types
    assert all(event.details in ("", None) or not str(event.details).startswith("{") for event in timeline)
    assert all(isinstance(event.metadata, dict) for event in timeline)

    second = advance_recovery(case_id)
    assert second.status == "recovered"
    assert second.can_advance is False

    timeline = get_case_timeline(case_id)
    types = [event.event_type for event in timeline]
    assert "adaptive_transition" in types

    recovered = get_recovered_queue()
    assert any(item.payment_id == "pay_tech_001" for item in recovered)
    metrics = get_metrics()
    assert metrics.revenue_recovered == 4500.0

    detail = get_case(case_id)
    assert detail.can_advance is False

    with pytest.raises(Exception):
        advance_recovery(case_id)


def test_nsf_recovers_and_permanent_can_escalate(seed_db):
    from fastapi import HTTPException
    from app.api.queue import advance_recovery, get_case_timeline, populate_demo_data

    populate_demo_data()

    nsf = advance_recovery("case_pay_nsf_002")
    assert nsf.status != "recovered"
    assert nsf.can_advance is True
    first_types = [event.event_type for event in get_case_timeline("case_pay_nsf_002")]
    assert "diagnosis" in first_types
    assert "adaptive_transition" not in first_types

    nsf_second = advance_recovery("case_pay_nsf_002")
    assert nsf_second.status == "recovered"
    second_types = [event.event_type for event in get_case_timeline("case_pay_nsf_002")]
    assert "adaptive_transition" in second_types
    assert "policy_decision" in second_types

    perm_first = advance_recovery("case_pay_perm_003")
    assert perm_first.status != "recovered"
    if perm_first.can_advance:
        perm_second = advance_recovery("case_pay_perm_003")
        assert perm_second.status in {"escalated", "failed", "recovered"}
    timeline = get_case_timeline("case_pay_perm_003")
    types = [event.event_type for event in timeline]
    assert "policy_decision" in types
    assert "diagnosis" in types

    with pytest.raises(HTTPException):
        advance_recovery("case_pay_nsf_002")
