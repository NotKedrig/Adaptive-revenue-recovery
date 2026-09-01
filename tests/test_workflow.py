"""
tests/test_workflow.py — Tests for the LangGraph workflow execution (Phase 2).
"""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.state.models import Base, Customer, Payment
from app.agents.diagnosis import DiagnosisResult


@pytest.fixture(scope="module")
def db_url(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("workflow_db")
    url = f"sqlite:///{tmp / 'test_workflow.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    # Seed test data
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Customer(customer_id="cust_wf_001", merchant_id="merch_wf"))
    session.add(Payment(
        payment_id="pay_wf_001",
        customer_id="cust_wf_001",
        amount=Decimal("3000.00"),
        currency="INR",
        payment_method="upi",
        failure_code="bank_timeout",
        failure_reason="Issuing bank did not respond",
    ))
    session.commit()
    session.close()
    return url


@patch("app.agents.diagnosis.get_provider")
@patch("app.agents.diagnosis._retrieve_diagnosis_context")
def test_full_graph_intake_to_diagnosis(mock_rag, mock_get_provider, db_url, monkeypatch):
    """Run the full Intake → Diagnosis graph with mocked LLM."""
    # Setup mocked DB
    import app.db.state.db as db_module
    original_get_engine = db_module.get_engine
    def patched_get_engine(database_url=None):
        return original_get_engine(db_url)
    monkeypatch.setattr(db_module, "get_engine", patched_get_engine)
    db_module._engine = None
    db_module._SessionLocal = None

    # Setup mocked LLM
    mock_rag.return_value = "Bank timeout: retry within 15 minutes."
    expected_diagnosis = DiagnosisResult(
        failure_category="transient_technical",
        root_cause="Bank authorization timed out",
        is_recoverable=True,
        recommended_action="immediate_retry",
        confidence=0.85,
        evidence=["Bank timeout code indicates transient issue"],
        retry_eligible=True,
        customer_action_required=False,
        urgency="low",
    )
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.text = expected_diagnosis.model_dump_json()
    mock_provider.complete.return_value = mock_response
    mock_get_provider.return_value = mock_provider

    # Build and run the graph
    from app.graph.workflow import build_graph
    graph = build_graph()

    input_state = {
        "messages": [],
        "runtime_metadata": [],
        "payment_id": "pay_wf_001",
        "failure_code": "bank_timeout",
        "failure_reason": "Issuing bank did not respond",
    }

    config = {"configurable": {"thread_id": "test_thread_wf_001"}}
    final_state = graph.invoke(input_state, config=config)

    # Assertions
    assert final_state["case_status"] == "diagnosed"
    assert final_state["diagnosis"]["failure_category"] == "transient_technical"
    assert final_state["diagnosis"]["is_recoverable"] is True
    assert final_state["diagnosis_confidence"] == 0.85
    assert final_state["amount"] == 3000.0
    assert final_state["customer_id"] == "cust_wf_001"
    assert len(final_state["messages"]) >= 2  # intake + diagnosis messages

    # Cleanup
    db_module._engine = None
    db_module._SessionLocal = None
