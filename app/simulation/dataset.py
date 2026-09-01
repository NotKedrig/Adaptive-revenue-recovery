"""
app/simulation/dataset.py — Synthetic Payment Dataset Generator (Phase 2).

Creates a deterministic, realistic dataset of failed payment cases with
variation across failure categories, amounts, methods, and customer profiles.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.simulation.interfaces import SimulatedPaymentEvent


# ---------------------------------------------------------------------------
# Failure profiles (category → probability weight, recovery difficulty)
# ---------------------------------------------------------------------------

FAILURE_PROFILES = [
    {
        "code": "insufficient_funds",
        "reason": "Customer's account did not have sufficient balance",
        "weight": 25,
        "recoverable": True,
        "methods": ["card", "upi", "netbanking"],
    },
    {
        "code": "expired_card",
        "reason": "Card has passed its expiration date",
        "weight": 15,
        "recoverable": False,  # requires customer action
        "methods": ["card"],
    },
    {
        "code": "invalid_card",
        "reason": "Card number or CVV is invalid",
        "weight": 8,
        "recoverable": False,
        "methods": ["card"],
    },
    {
        "code": "bank_timeout",
        "reason": "Issuing bank did not respond within the timeout period",
        "weight": 18,
        "recoverable": True,
        "methods": ["card", "upi", "netbanking"],
    },
    {
        "code": "authentication_failed",
        "reason": "3D Secure or OTP authentication was not completed",
        "weight": 12,
        "recoverable": True,  # via payment link
        "methods": ["card", "upi"],
    },
    {
        "code": "issuer_decline",
        "reason": "Transaction declined by issuing bank (Do Not Honor)",
        "weight": 10,
        "recoverable": True,  # sometimes
        "methods": ["card", "netbanking"],
    },
    {
        "code": "recurring_payment_failure",
        "reason": "Scheduled recurring debit could not be processed",
        "weight": 8,
        "recoverable": True,
        "methods": ["card", "upi"],
    },
    {
        "code": "network_error",
        "reason": "Network connectivity failure between gateway and bank",
        "weight": 4,
        "recoverable": True,
        "methods": ["card", "upi", "netbanking"],
    },
]

CARD_NETWORKS = ["Visa", "Mastercard", "RuPay", "Amex"]
ISSUER_BANKS = [
    "HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank",
    "Kotak Mahindra Bank", "Yes Bank", "Punjab National Bank",
    "Bank of Baroda", "IndusInd Bank", "IDFC First Bank"
]
MERCHANT_IDS = [
    "merch_streaming_001", "merch_saas_002", "merch_ecomm_003",
    "merch_food_004", "merch_insurance_005"
]

# Amount distributions by merchant type
AMOUNT_RANGES = {
    "merch_streaming_001": (149, 1999),     # Streaming subscriptions
    "merch_saas_002": (499, 49999),          # SaaS plans
    "merch_ecomm_003": (99, 25000),          # E-commerce purchases
    "merch_food_004": (50, 2500),            # Food delivery
    "merch_insurance_005": (1000, 100000),   # Insurance premiums
}


def _generate_customer_id(rng: random.Random, idx: int) -> str:
    """Generate a deterministic customer ID."""
    return f"cust_{rng.randint(1000, 9999)}_{idx:03d}"


def _generate_payment_id(rng: random.Random) -> str:
    """Generate a deterministic payment ID."""
    return f"pay_{rng.randint(100000, 999999)}"


def _pick_failure(rng: random.Random) -> dict:
    """Select a failure profile weighted by frequency."""
    total = sum(fp["weight"] for fp in FAILURE_PROFILES)
    roll = rng.uniform(0, total)
    cumulative = 0
    for fp in FAILURE_PROFILES:
        cumulative += fp["weight"]
        if roll <= cumulative:
            return fp
    return FAILURE_PROFILES[-1]


def _pick_amount(rng: random.Random, merchant_id: str) -> float:
    """Generate a realistic payment amount for the merchant type."""
    lo, hi = AMOUNT_RANGES.get(merchant_id, (100, 10000))
    # Use a log-normal-ish distribution (more small payments than large)
    raw = rng.lognormvariate(0, 1)
    scaled = lo + (hi - lo) * min(raw / 5.0, 1.0)
    return round(scaled, 2)


def generate_dataset(
    n: int = 50,
    seed: int = 42,
    base_time: datetime | None = None,
) -> list[SimulatedPaymentEvent]:
    """
    Generate n synthetic failed payment events.

    Args:
        n:         Number of events to generate.
        seed:      Random seed for deterministic reproducibility.
        base_time: Anchor timestamp; events are spread over the preceding 7 days.

    Returns:
        List of SimulatedPaymentEvent, sorted by timestamp.
    """
    rng = random.Random(seed)
    base = base_time or datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    events: list[SimulatedPaymentEvent] = []

    # Pre-generate a pool of customers (some will have multiple failures)
    num_customers = max(n // 3, 10)
    customer_pool = [_generate_customer_id(rng, i) for i in range(num_customers)]

    for i in range(n):
        failure = _pick_failure(rng)
        merchant_id = rng.choice(MERCHANT_IDS)
        customer_id = rng.choice(customer_pool)
        payment_method = rng.choice(failure["methods"])

        card_network = None
        issuer_bank = None
        if payment_method == "card":
            card_network = rng.choice(CARD_NETWORKS)
            issuer_bank = rng.choice(ISSUER_BANKS)
        elif payment_method == "netbanking":
            issuer_bank = rng.choice(ISSUER_BANKS)

        amount = _pick_amount(rng, merchant_id)
        # Spread events over the last 7 days
        offset_seconds = rng.randint(0, 7 * 24 * 3600)
        timestamp = base - timedelta(seconds=offset_seconds)

        events.append(SimulatedPaymentEvent(
            payment_id=_generate_payment_id(rng),
            customer_id=customer_id,
            merchant_id=merchant_id,
            amount=amount,
            currency="INR",
            payment_method=payment_method,
            card_network=card_network,
            issuer_bank=issuer_bank,
            failure_code=failure["code"],
            failure_reason=failure["reason"],
            timestamp=timestamp.isoformat(),
        ))

    events.sort(key=lambda e: e.timestamp)
    return events
