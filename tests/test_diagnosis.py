"""
tests/test_diagnosis.py — Tests for the Diagnosis Agent (with mocked LLM).
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.agents.diagnosis import (
    DiagnosisResult,
    run_diagnosis,
    diagnosis_node,
    _fallback_diagnosis,
    _parse_diagnosis_response,
)
from app.graph.state import RecoveryState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_state(failure_code: str, failure_reason: str = "", **kwargs) -> RecoveryState:
    base = {
        "messages": [],
        "runtime_metadata": [],
        "payment_id": "pay_test_001",
        "customer_id": "cust_test_001",
        "merchant_id": "merch_test",
        "amount": 1500.0,
        "currency": "INR",
        "payment_method": "card",
        "card_network": "Visa",
        "issuer_bank": "HDFC Bank",
        "failure_code": failure_code,
        "failure_reason": failure_reason or f"Test failure: {failure_code}",
        "attempt_count": 0,
    }
    base.update(kwargs)
    return base


def _mock_llm_response(diagnosis: DiagnosisResult):
    """Create a mock LLM provider that returns the given diagnosis as JSON."""
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.text = diagnosis.model_dump_json()
    mock_provider.complete.return_value = mock_response
    return mock_provider


# ---------------------------------------------------------------------------
# Fallback diagnosis tests (no LLM needed)
# ---------------------------------------------------------------------------

class TestFallbackDiagnosis:
    def test_bank_timeout_is_recoverable(self):
        d = _fallback_diagnosis("bank_timeout", "Bank did not respond")
        assert d.is_recoverable is True
        assert d.retry_eligible is True
        assert d.failure_category == "transient_technical"

    def test_expired_card_not_recoverable_by_retry(self):
        d = _fallback_diagnosis("expired_card", "Card expired")
        assert d.retry_eligible is False
        assert d.customer_action_required is True
        assert d.failure_category == "permanent_card"

    def test_invalid_card_not_recoverable(self):
        d = _fallback_diagnosis("invalid_card", "Invalid card number")
        assert d.retry_eligible is False
        assert d.customer_action_required is True

    def test_network_error_very_high_confidence(self):
        d = _fallback_diagnosis("network_error", "Connection timeout")
        assert d.confidence >= 0.9
        assert d.retry_eligible is True

    def test_insufficient_funds_delayed_retry(self):
        d = _fallback_diagnosis("insufficient_funds", "NSF")
        assert d.recommended_action == "delayed_retry"
        assert d.is_recoverable is True

    def test_unknown_code_escalates(self):
        d = _fallback_diagnosis("some_unknown_code", "Mystery error")
        assert d.recommended_action == "escalate_to_human"
        assert d.confidence <= 0.3

    def test_authentication_failure_needs_customer(self):
        d = _fallback_diagnosis("authentication_failed", "OTP failed")
        assert d.customer_action_required is True
        assert d.recommended_action == "notify_customer"


# ---------------------------------------------------------------------------
# Structured output parsing
# ---------------------------------------------------------------------------

class TestParseDiagnosisResponse:
    def test_parses_valid_json(self):
        data = DiagnosisResult(
            failure_category="transient_technical",
            root_cause="Bank timeout",
            is_recoverable=True,
            recommended_action="immediate_retry",
            confidence=0.9,
            evidence=["Bank was slow"],
            retry_eligible=True,
            customer_action_required=False,
            urgency="low",
        )
        result = _parse_diagnosis_response(data.model_dump_json())
        assert result.failure_category == "transient_technical"
        assert result.confidence == 0.9

    def test_parses_json_with_code_fences(self):
        data = DiagnosisResult(
            failure_category="permanent_card",
            root_cause="Card expired",
            is_recoverable=False,
            recommended_action="request_new_payment_method",
            confidence=0.85,
        )
        wrapped = f"```json\n{data.model_dump_json()}\n```"
        result = _parse_diagnosis_response(wrapped)
        assert result.failure_category == "permanent_card"


# ---------------------------------------------------------------------------
# Full diagnosis with mocked LLM
# ---------------------------------------------------------------------------

class TestDiagnosisWithMockedLLM:
    @patch("app.agents.diagnosis.get_provider")
    @patch("app.agents.diagnosis._retrieve_diagnosis_context")
    def test_bank_timeout_diagnosis(self, mock_rag, mock_get_provider):
        mock_rag.return_value = "Bank timeout is transient. Retry within 15 minutes."

        expected = DiagnosisResult(
            failure_category="transient_technical",
            root_cause="Issuing bank authorization system timed out",
            is_recoverable=True,
            recommended_action="immediate_retry",
            confidence=0.88,
            evidence=["Bank timeout code", "RAG: retry within 15 minutes"],
            retry_eligible=True,
            customer_action_required=False,
            urgency="low",
        )
        mock_get_provider.return_value = _mock_llm_response(expected)

        state = _make_state("bank_timeout", "Bank did not respond within timeout")
        result = run_diagnosis(state)

        assert result.failure_category == "transient_technical"
        assert result.is_recoverable is True
        assert result.retry_eligible is True

    @patch("app.agents.diagnosis.get_provider")
    @patch("app.agents.diagnosis._retrieve_diagnosis_context")
    def test_expired_card_diagnosis(self, mock_rag, mock_get_provider):
        mock_rag.return_value = "Expired cards cannot be retried."

        expected = DiagnosisResult(
            failure_category="permanent_card",
            root_cause="Card has passed its expiration date",
            is_recoverable=False,
            recommended_action="request_new_payment_method",
            confidence=0.92,
            evidence=["Card expiration date check"],
            retry_eligible=False,
            customer_action_required=True,
            urgency="high",
        )
        mock_get_provider.return_value = _mock_llm_response(expected)

        state = _make_state("expired_card", "Card has expired")
        result = run_diagnosis(state)

        assert result.failure_category == "permanent_card"
        assert result.is_recoverable is False
        assert result.customer_action_required is True

    @patch("app.agents.diagnosis.get_provider")
    @patch("app.agents.diagnosis._retrieve_diagnosis_context")
    def test_diagnosis_node_updates_state(self, mock_rag, mock_get_provider):
        mock_rag.return_value = ""

        expected = DiagnosisResult(
            failure_category="transient_customer",
            root_cause="Insufficient balance",
            is_recoverable=True,
            recommended_action="delayed_retry",
            confidence=0.7,
            retry_eligible=True,
        )
        mock_get_provider.return_value = _mock_llm_response(expected)

        state = _make_state("insufficient_funds")
        result = diagnosis_node(state)

        assert result["case_status"] == "diagnosed"
        assert result["diagnosis"]["failure_category"] == "transient_customer"
        assert result["diagnosis_confidence"] == 0.7
        assert len(result["messages"]) == 1
        assert len(result["runtime_metadata"]) == 1

    @patch("app.agents.diagnosis.get_provider")
    @patch("app.agents.diagnosis._retrieve_diagnosis_context")
    def test_llm_parse_failure_falls_back(self, mock_rag, mock_get_provider):
        """When LLM returns unparseable output, fallback diagnosis is used."""
        mock_rag.return_value = ""

        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is not valid JSON at all!"
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        state = _make_state("bank_timeout")
        result = run_diagnosis(state)

        # Should get the fallback diagnosis
        assert result.failure_category == "transient_technical"
        assert result.confidence == 0.85  # fallback confidence for bank_timeout
