"""
app/agents/diagnosis.py — Diagnosis Agent (Phase 2).

Inspects a failed payment's context, retrieves relevant knowledge from the RAG
knowledge base, classifies the failure, determines recoverability, and produces
a structured DiagnosisResult.

This agent NEVER directly executes financial actions.
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.graph.state import RecoveryState
from app.llm.provider import get_provider, LLMResponse
from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured Output Schema
# ---------------------------------------------------------------------------

class DiagnosisResult(BaseModel):
    """Structured diagnosis output produced by the Diagnosis Agent."""

    failure_category: str = Field(
        ...,
        description=(
            "High-level failure classification. One of: "
            "'transient_technical', 'transient_customer', "
            "'permanent_card', 'permanent_fraud', 'ambiguous_decline', "
            "'recurring_failure'"
        ),
    )
    root_cause: str = Field(
        ...,
        description="Concise root cause explanation (1-2 sentences).",
    )
    is_recoverable: bool = Field(
        ...,
        description="Whether the payment can potentially be recovered.",
    )
    recommended_action: str = Field(
        ...,
        description=(
            "Primary recommended recovery action. One of: "
            "'immediate_retry', 'delayed_retry', 'notify_customer', "
            "'request_new_payment_method', 'escalate_to_human', "
            "'close_non_recoverable'"
        ),
    )
    confidence: float = Field(
        ...,
        description="Confidence score for this diagnosis (0.0 to 1.0).",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting evidence or reasoning steps.",
    )
    retry_eligible: bool = Field(
        default=False,
        description="Whether an automated payment retry is appropriate.",
    )
    customer_action_required: bool = Field(
        default=False,
        description="Whether the customer needs to take action (update card, re-auth, etc.).",
    )
    urgency: str = Field(
        default="medium",
        description="Urgency level: 'low', 'medium', 'high', 'critical'.",
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

DIAGNOSIS_SYSTEM_PROMPT = """You are a Payment Failure Diagnosis Agent for an AI Revenue Recovery system.

Your role is to analyze failed payment events and produce a structured diagnosis. You must:
1. Classify the failure into the correct category
2. Identify the root cause
3. Determine if the payment is recoverable
4. Recommend the best immediate recovery action
5. Assign a confidence score based on available evidence
6. Provide concise evidence/reasoning

IMPORTANT RULES:
- NEVER execute or authorize any financial action
- NEVER guess at card numbers, account details, or personal information
- Base your diagnosis on the failure code, payment context, and knowledge base evidence
- If evidence is ambiguous, lower your confidence score accordingly
- Flag fraud indicators if detected

You will receive:
1. Payment failure details (failure code, amount, method, bank, etc.)
2. Knowledge base excerpts about the failure code and recovery strategies

Respond with a JSON object matching the DiagnosisResult schema exactly."""


def _build_diagnosis_prompt(state: RecoveryState, rag_context: str) -> str:
    """Build the full prompt for the diagnosis LLM call."""
    payment_context = f"""
## Payment Failure Details

- **Payment ID:** {state.get('payment_id', 'unknown')}
- **Customer ID:** {state.get('customer_id', 'unknown')}
- **Amount:** {state.get('amount', 0)} {state.get('currency', 'INR')}
- **Payment Method:** {state.get('payment_method', 'unknown')}
- **Card Network:** {state.get('card_network', 'N/A')}
- **Issuer Bank:** {state.get('issuer_bank', 'N/A')}
- **Failure Code:** {state.get('failure_code', 'unknown')}
- **Failure Reason:** {state.get('failure_reason', 'unknown')}
- **Attempt Count:** {state.get('attempt_count', 0)}
"""

    return f"""{DIAGNOSIS_SYSTEM_PROMPT}

{payment_context}

## Knowledge Base Reference

{rag_context if rag_context else "No relevant knowledge base entries found."}

## Task

Analyze the payment failure above and produce a DiagnosisResult JSON object.

Respond ONLY with valid JSON matching this schema:
{{
    "failure_category": "string",
    "root_cause": "string",
    "is_recoverable": boolean,
    "recommended_action": "string",
    "confidence": float (0.0 to 1.0),
    "evidence": ["string", ...],
    "retry_eligible": boolean,
    "customer_action_required": boolean,
    "urgency": "string"
}}"""


# ---------------------------------------------------------------------------
# RAG retrieval helper
# ---------------------------------------------------------------------------

def _retrieve_diagnosis_context(failure_code: str, failure_reason: str) -> str:
    """Retrieve relevant knowledge base context for the diagnosis."""
    try:
        from app.rag.retriever import retrieve

        collection_name = f"recovery_kb_{settings.chunking_strategy}"
        query = f"payment failure {failure_code}: {failure_reason}"

        chunks = retrieve(
            query=query,
            collection_name=collection_name,
            top_k=3,
            chroma_persist_dir=settings.chroma_persist_dir,
        )

        if chunks:
            context_parts = []
            for chunk in chunks:
                context_parts.append(
                    f"### Source: {chunk.title} (relevance: {chunk.similarity_score:.2f})\n"
                    f"{chunk.text}\n"
                )
            return "\n---\n".join(context_parts)
    except Exception as e:
        logger.warning(f"RAG retrieval failed (continuing without context): {e}")

    return ""


# ---------------------------------------------------------------------------
# Core diagnosis function
# ---------------------------------------------------------------------------

def _parse_diagnosis_response(text: str) -> DiagnosisResult:
    """Parse the LLM response text into a DiagnosisResult."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    data = json.loads(cleaned)
    return DiagnosisResult(**data)


def run_diagnosis(state: RecoveryState, force_local: bool = True) -> DiagnosisResult:
    """
    Run the diagnosis agent on the current RecoveryState.

    By default (force_local=True), this uses a deterministic local rule engine
    based on the failure code to avoid external LLM dependencies, ensuring
    offline reliability and speed.
    """
    failure_code = state.get("failure_code", "unknown")
    failure_reason = state.get("failure_reason", "unknown")

    # For Phase 2, we enforce deterministic local execution by default.
    if force_local or getattr(settings, "local_diagnosis_only", True):
        logger.info(
            "Running deterministic local diagnosis",
            extra={"failure_code": failure_code}
        )
        diagnosis = _fallback_diagnosis(failure_code, failure_reason)
        return diagnosis

    # --- External LLM Path (Optional Infrastructure) ---
    # 1. Retrieve relevant context from the knowledge base
    rag_context = _retrieve_diagnosis_context(failure_code, failure_reason)
    logger.info(
        "Diagnosis RAG context retrieved",
        extra={"failure_code": failure_code, "has_context": bool(rag_context)},
    )

    # 2. Build prompt and call LLM
    prompt = _build_diagnosis_prompt(state, rag_context)
    provider = get_provider()
    
    try:
        llm_response: LLMResponse = provider.complete(
            prompt=prompt,
            temperature=0.0,
            use_cache=True,
        )
        # 3. Parse structured output
        diagnosis = _parse_diagnosis_response(llm_response.text)
    except Exception as e:
        logger.error(f"Failed to call LLM or parse response: {e}. Falling back to local rules.")
        diagnosis = _fallback_diagnosis(failure_code, failure_reason)

    logger.info(
        "Diagnosis complete",
        extra={
            "failure_code": failure_code,
            "category": diagnosis.failure_category,
            "recoverable": diagnosis.is_recoverable,
            "confidence": diagnosis.confidence,
            "recommended_action": diagnosis.recommended_action,
        },
    )
    return diagnosis


def _fallback_diagnosis(failure_code: str, failure_reason: str) -> DiagnosisResult:
    """
    Rule-based fallback when LLM parsing fails.
    Ensures the pipeline always produces a valid diagnosis.
    """
    FALLBACK_MAP = {
        "insufficient_funds": DiagnosisResult(
            failure_category="transient_customer",
            root_cause="Customer account had insufficient funds at time of charge.",
            is_recoverable=True,
            recommended_action="delayed_retry",
            confidence=0.7,
            evidence=["Rule-based fallback: insufficient_funds is typically transient"],
            retry_eligible=True,
            customer_action_required=False,
            urgency="medium",
        ),
        "expired_card": DiagnosisResult(
            failure_category="permanent_card",
            root_cause="Card has expired and requires customer to provide updated details.",
            is_recoverable=False,
            recommended_action="request_new_payment_method",
            confidence=0.9,
            evidence=["Rule-based fallback: expired card cannot be retried"],
            retry_eligible=False,
            customer_action_required=True,
            urgency="high",
        ),
        "invalid_card": DiagnosisResult(
            failure_category="permanent_card",
            root_cause="Card details are invalid; possible typo or cancelled card.",
            is_recoverable=False,
            recommended_action="request_new_payment_method",
            confidence=0.85,
            evidence=["Rule-based fallback: invalid card cannot be retried"],
            retry_eligible=False,
            customer_action_required=True,
            urgency="medium",
        ),
        "bank_timeout": DiagnosisResult(
            failure_category="transient_technical",
            root_cause="Bank authorization system timed out; likely transient.",
            is_recoverable=True,
            recommended_action="immediate_retry",
            confidence=0.85,
            evidence=["Rule-based fallback: bank timeout is almost always transient"],
            retry_eligible=True,
            customer_action_required=False,
            urgency="low",
        ),
        "authentication_failed": DiagnosisResult(
            failure_category="transient_customer",
            root_cause="Customer did not complete authentication (OTP/3DS).",
            is_recoverable=True,
            recommended_action="notify_customer",
            confidence=0.7,
            evidence=["Rule-based fallback: auth failure requires customer re-attempt"],
            retry_eligible=False,
            customer_action_required=True,
            urgency="high",
        ),
        "issuer_decline": DiagnosisResult(
            failure_category="ambiguous_decline",
            root_cause="Issuing bank declined the transaction without specific reason.",
            is_recoverable=True,
            recommended_action="delayed_retry",
            confidence=0.4,
            evidence=["Rule-based fallback: generic decline has unclear root cause"],
            retry_eligible=True,
            customer_action_required=False,
            urgency="medium",
        ),
        "recurring_payment_failure": DiagnosisResult(
            failure_category="recurring_failure",
            root_cause="Scheduled recurring payment could not be processed.",
            is_recoverable=True,
            recommended_action="notify_customer",
            confidence=0.6,
            evidence=["Rule-based fallback: recurring failure needs investigation"],
            retry_eligible=True,
            customer_action_required=False,
            urgency="high",
        ),
        "network_error": DiagnosisResult(
            failure_category="transient_technical",
            root_cause="Network-level error; no financial transaction initiated.",
            is_recoverable=True,
            recommended_action="immediate_retry",
            confidence=0.95,
            evidence=["Rule-based fallback: network errors are transient by definition"],
            retry_eligible=True,
            customer_action_required=False,
            urgency="low",
        ),
    }

    return FALLBACK_MAP.get(
        failure_code,
        DiagnosisResult(
            failure_category="ambiguous_decline",
            root_cause=f"Unknown failure code: {failure_code}. {failure_reason}",
            is_recoverable=True,
            recommended_action="escalate_to_human",
            confidence=0.2,
            evidence=[f"Rule-based fallback: unrecognized failure code '{failure_code}'"],
            retry_eligible=False,
            customer_action_required=False,
            urgency="high",
        ),
    )


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------

def diagnosis_node(state: RecoveryState) -> dict:
    """
    LangGraph node: runs the diagnosis agent and updates RecoveryState.
    """
    diagnosis = run_diagnosis(state)

    return {
        "diagnosis": diagnosis.model_dump(),
        "diagnosis_confidence": diagnosis.confidence,
        "case_status": "diagnosed",
        "messages": [{
            "role": "assistant",
            "content": (
                f"Diagnosis complete: {diagnosis.failure_category} — "
                f"{diagnosis.root_cause} "
                f"(confidence: {diagnosis.confidence:.0%}, "
                f"recoverable: {diagnosis.is_recoverable})"
            ),
        }],
        "runtime_metadata": [{
            "agent": "diagnosis",
            "failure_category": diagnosis.failure_category,
            "confidence": diagnosis.confidence,
            "recommended_action": diagnosis.recommended_action,
        }],
    }
