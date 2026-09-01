"""
app/agents/intake.py — Intake Node (Phase 2).

Accepts a failed payment event, loads the associated customer/payment/recovery
case from the database, initializes RecoveryState fields, creates an audit
event, and determines whether the case is eligible for recovery processing.
"""

import logging
from datetime import datetime, timezone

from app.graph.state import RecoveryState
from app.db.state.db import get_session
from app.db.state.models import (
    Customer,
    Payment,
    RecoveryCase,
    RecoveryEvent,
    AuditLog,
)

logger = logging.getLogger(__name__)

# Cases with these statuses should not be re-processed
NON_ELIGIBLE_STATUSES = {"recovered", "failed", "escalated", "closed"}

# Maximum attempts before automatic escalation
MAX_ATTEMPTS_DEFAULT = 5


def intake_node(state: RecoveryState) -> dict:
    """
    LangGraph node: intake processing for a failed payment.

    Expects state to contain at minimum:
        - payment_id
        - failure_code
        - failure_reason

    Populates the full RecoveryState with customer/payment context from the
    database, creates audit events, and determines eligibility.
    """
    payment_id = state.get("payment_id", "")
    if not payment_id:
        logger.error("Intake node received state without payment_id")
        return {
            "case_status": "error",
            "messages": [{
                "role": "system",
                "content": "Intake error: no payment_id provided.",
            }],
        }

    with get_session() as db:
        # Load payment
        payment = db.query(Payment).filter_by(payment_id=payment_id).first()
        if not payment:
            logger.warning(f"Payment {payment_id} not found in database")
            return {
                "case_status": "error",
                "messages": [{
                    "role": "system",
                    "content": f"Intake error: payment {payment_id} not found.",
                }],
            }

        # Load customer
        customer = db.query(Customer).filter_by(customer_id=payment.customer_id).first()

        # Load or create recovery case
        case_id = f"case_{payment_id}"
        case = db.query(RecoveryCase).filter_by(case_id=case_id).first()

        if not case:
            case = RecoveryCase(
                case_id=case_id,
                payment_id=payment_id,
                status="open",
                escalation_level=0,
            )
            db.add(case)
            db.flush()

        # Check eligibility
        eligible = case.status not in NON_ELIGIBLE_STATUSES

        # Count prior attempts
        from app.db.state.models import RecoveryAttempt
        attempt_count = (
            db.query(RecoveryAttempt)
            .filter_by(case_id=case_id)
            .count()
        )

        # Create audit event
        audit = AuditLog(
            action="intake_processed",
            resource_type="recovery_case",
            resource_id=case_id,
            details={
                "payment_id": payment_id,
                "eligible": eligible,
                "attempt_count": attempt_count,
                "failure_code": payment.failure_code,
            },
        )
        db.add(audit)

        # Create recovery event
        event = RecoveryEvent(
            case_id=case_id,
            event_type="intake_complete",
            agent_name="intake",
            event_data={
                "eligible": eligible,
                "reason": "case_open" if eligible else f"status_{case.status}",
            },
        )
        db.add(event)
        db.commit()
        # Extract fields before the session closes to prevent DetachedInstanceError
        result_data = {
            "payment_id": payment_id,
            "customer_id": payment.customer_id,
            "merchant_id": customer.merchant_id if customer else "",
            "amount": float(payment.amount),
            "currency": payment.currency,
            "failure_code": payment.failure_code,
            "failure_reason": payment.failure_reason,
            "payment_method": payment.payment_method,
            "card_network": payment.card_network,
            "issuer_bank": payment.issuer_bank,
            "case_status": case.status,
            "escalation_level": case.escalation_level,
        }
        
    # Build the output state update
    result: dict = {
        "payment_id": payment_id,
        "customer_id": result_data["customer_id"],
        "merchant_id": result_data["merchant_id"],
        "amount": result_data["amount"],
        "currency": result_data["currency"],
        "failure_code": result_data["failure_code"] or state.get("failure_code", ""),
        "failure_reason": result_data["failure_reason"] or state.get("failure_reason", ""),
        "payment_method": result_data["payment_method"] or "",
        "card_network": result_data["card_network"] or "",
        "issuer_bank": result_data["issuer_bank"] or "",
        "case_status": "intake_complete" if eligible else result_data["case_status"],
        "escalation_level": result_data["escalation_level"],
        "attempt_count": attempt_count,
        "max_attempts": MAX_ATTEMPTS_DEFAULT,
        "safety_cleared": False,
        "safety_flags": [],
        "messages": [{
            "role": "system",
            "content": (
                f"Intake complete for payment {payment_id}. "
                f"Failure: {result_data['failure_code']}. "
                f"Amount: {result_data['amount']} {result_data['currency']}. "
                f"{'Eligible for recovery.' if eligible else f'Not eligible (status: {result_data['case_status']}).'}"
            ),
        }],
        "runtime_metadata": [{
            "agent": "intake",
            "case_id": case_id,
            "eligible": eligible,
            "attempt_count": attempt_count,
        }],
    }

    # If not eligible, route to END
    if not eligible:
        result["next_agent"] = "__end__"

    logger.info(
        "Intake complete",
        extra={
            "payment_id": payment_id,
            "case_id": case_id,
            "eligible": eligible,
            "attempt_count": attempt_count,
        },
    )
    return result
