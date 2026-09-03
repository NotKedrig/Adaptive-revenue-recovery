"""
tests/test_state.py - Tests for the new Revenue Recovery State.
"""

from app.graph.state import RecoveryState

def test_recovery_state_initialization():
    """Verify the LangGraph state can be constructed properly."""
    
    state: RecoveryState = {
        "messages": [],
        "payment_id": "pay_123",
        "merchant_id": "merch_abc",
        "customer_id": "cust_456",
        "amount": 1000.0,
        "currency": "INR",
        "failure_code": "insufficient_funds",
        "failure_reason": "Not enough balance",
        "payment_method": "upi",
        "card_network": "",
        "issuer_bank": "HDFC",
        "diagnosis": {},
        "diagnosis_confidence": 0.0,
        "recovery_strategy": {},
        "recovery_actions": [],
        "current_action": {},
        "outcome_signal": "",
        "escalation_level": 0,
        "case_status": "open",
        "safety_cleared": False,
        "safety_flags": [],
        "attempt_count": 0,
        "max_attempts": 3,
        "runtime_metadata": [],
        "next_agent": "intake"
    }
    
    assert state["payment_id"] == "pay_123"
    assert state["amount"] == 1000.0
    assert state["failure_code"] == "insufficient_funds"
    assert state["case_status"] == "open"
