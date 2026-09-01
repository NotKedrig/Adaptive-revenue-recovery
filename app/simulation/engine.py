"""
app/simulation/engine.py — Local Payment/Customer Simulation Engine (Phase 2).

Provides a deterministic simulation of payment recovery outcomes without
real payment APIs, email, SMS, or external services.
"""

import random
import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.db.state.db import get_session
from app.db.state.models import Customer, Payment, RecoveryCase, RecoveryAttempt, RecoveryEvent
from app.simulation.interfaces import (
    SimulatedPaymentEvent,
    RecoveryActionRequest,
    RecoveryActionResponse,
    SimulatedCustomerResponse,
    SimulatedPaymentOutcome,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Recovery probability model (deterministic given seed + failure code)
# ---------------------------------------------------------------------------

RECOVERY_PROBABILITIES = {
    # failure_code → {action_type → base_probability}
    "insufficient_funds": {"retry": 0.45, "notify_email": 0.25, "notify_sms": 0.30},
    "expired_card":       {"retry": 0.0,  "notify_email": 0.30, "notify_sms": 0.20},
    "invalid_card":       {"retry": 0.0,  "notify_email": 0.10, "notify_sms": 0.05},
    "bank_timeout":       {"retry": 0.80, "notify_email": 0.10, "notify_sms": 0.10},
    "authentication_failed": {"retry": 0.05, "notify_email": 0.35, "notify_sms": 0.40},
    "issuer_decline":     {"retry": 0.20, "notify_email": 0.15, "notify_sms": 0.10},
    "recurring_payment_failure": {"retry": 0.30, "notify_email": 0.35, "notify_sms": 0.30},
    "network_error":      {"retry": 0.90, "notify_email": 0.05, "notify_sms": 0.05},
}

CUSTOMER_RESPONSE_TYPES = ["clicked_link", "ignored", "replied_stop"]
CUSTOMER_RESPONSE_WEIGHTS = {
    "notify_email": [0.25, 0.70, 0.05],
    "notify_sms":   [0.35, 0.55, 0.10],
}


class SimulationEngine:
    """
    Deterministic simulation engine for payment recovery scenarios.

    All outcomes are derived from a seeded PRNG so that test scenarios
    are fully reproducible.
    """

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
        self._attempt_counter = 0

    def load_payment_event(
        self,
        event: SimulatedPaymentEvent,
        database_url: str | None = None,
    ) -> str:
        """
        Persist a simulated payment event to the database, creating Customer,
        Payment, and RecoveryCase records.

        Returns:
            The case_id of the created RecoveryCase.
        """
        case_id = f"case_{event.payment_id}"

        with get_session(database_url) as db:
            # Upsert customer
            customer = db.query(Customer).filter_by(customer_id=event.customer_id).first()
            if not customer:
                customer = Customer(
                    customer_id=event.customer_id,
                    merchant_id=event.merchant_id,
                )
                db.add(customer)
                db.flush()

            # Create payment
            existing_payment = db.query(Payment).filter_by(payment_id=event.payment_id).first()
            if not existing_payment:
                payment = Payment(
                    payment_id=event.payment_id,
                    customer_id=event.customer_id,
                    amount=Decimal(str(event.amount)),
                    currency=event.currency,
                    payment_method=event.payment_method,
                    card_network=event.card_network,
                    issuer_bank=event.issuer_bank,
                    failure_code=event.failure_code,
                    failure_reason=event.failure_reason,
                )
                db.add(payment)
                db.flush()

            # Create recovery case
            existing_case = db.query(RecoveryCase).filter_by(case_id=case_id).first()
            if not existing_case:
                case = RecoveryCase(
                    case_id=case_id,
                    payment_id=event.payment_id,
                    status="open",
                    escalation_level=0,
                )
                db.add(case)
                db.flush()

            # Create initial event
            init_event = RecoveryEvent(
                case_id=case_id,
                event_type="case_created",
                agent_name="simulation_engine",
                event_data={
                    "failure_code": event.failure_code,
                    "failure_reason": event.failure_reason,
                    "amount": event.amount,
                    "payment_method": event.payment_method,
                },
            )
            db.add(init_event)
            db.commit()

        logger.info(f"Loaded payment event {event.payment_id} → case {case_id}")
        return case_id

    def execute_recovery_action(
        self,
        request: RecoveryActionRequest,
        failure_code: str,
        database_url: str | None = None,
    ) -> RecoveryActionResponse:
        """
        Simulate executing a recovery action (retry, email, SMS).

        The outcome is deterministic given the engine's seed and the
        number of prior calls.
        """
        self._attempt_counter += 1

        probs = RECOVERY_PROBABILITIES.get(failure_code, {})
        base_prob = probs.get(request.action_type, 0.1)

        # Technical success means the action executed (e.g., SMS was delivered)
        # Not whether the payment was recovered
        if request.action_type == "retry":
            tech_success = self._rng.random() < base_prob
        else:
            # Notifications almost always deliver technically
            tech_success = self._rng.random() < 0.95

        response = RecoveryActionResponse(
            success=tech_success,
            message=f"Simulated {request.action_type}: {'delivered' if tech_success else 'failed'}",
            provider_id=f"sim_provider_{self._attempt_counter}",
        )

        # Persist attempt
        with get_session(database_url) as db:
            attempt = RecoveryAttempt(
                case_id=request.case_id,
                action_type=request.action_type,
                status="success" if tech_success else "failure",
                request_payload=request.payload,
                response_payload=response.model_dump(),
            )
            db.add(attempt)
            db.commit()

        return response

    def generate_customer_response(
        self,
        case_id: str,
        customer_id: str,
        action_type: str,
    ) -> SimulatedCustomerResponse:
        """
        Simulate a customer's reaction to a notification.
        """
        weights = CUSTOMER_RESPONSE_WEIGHTS.get(action_type, [0.2, 0.7, 0.1])
        response_type = self._rng.choices(
            CUSTOMER_RESPONSE_TYPES,
            weights=weights,
            k=1,
        )[0]

        return SimulatedCustomerResponse(
            case_id=case_id,
            customer_id=customer_id,
            response_type=response_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def generate_payment_outcome(
        self,
        case_id: str,
        failure_code: str,
        action_type: str,
        amount: float,
    ) -> SimulatedPaymentOutcome:
        """
        Generate the final payment outcome for a recovery attempt.
        """
        self._attempt_counter += 1
        attempt_id = f"attempt_{self._attempt_counter}"

        probs = RECOVERY_PROBABILITIES.get(failure_code, {})
        recovery_prob = probs.get(action_type, 0.1)

        roll = self._rng.random()
        if roll < recovery_prob:
            status = "success"
            amount_recovered = amount
            error_code = None
        elif roll < recovery_prob + 0.1:
            status = "partial"
            amount_recovered = round(amount * self._rng.uniform(0.3, 0.8), 2)
            error_code = None
        else:
            status = "failed"
            amount_recovered = 0.0
            error_code = failure_code

        return SimulatedPaymentOutcome(
            case_id=case_id,
            attempt_id=attempt_id,
            status=status,
            amount_recovered=amount_recovered,
            error_code=error_code,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
