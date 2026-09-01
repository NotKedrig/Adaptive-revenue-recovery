"""
tests/test_dataset.py — Tests for synthetic payment dataset generation.
"""
import pytest
from app.simulation.dataset import generate_dataset, FAILURE_PROFILES


def test_generates_correct_count():
    events = generate_dataset(n=20, seed=42)
    assert len(events) == 20


def test_deterministic_with_same_seed():
    events_a = generate_dataset(n=10, seed=123)
    events_b = generate_dataset(n=10, seed=123)
    for a, b in zip(events_a, events_b):
        assert a.payment_id == b.payment_id
        assert a.customer_id == b.customer_id
        assert a.amount == b.amount
        assert a.failure_code == b.failure_code


def test_different_seeds_produce_different_data():
    events_a = generate_dataset(n=10, seed=1)
    events_b = generate_dataset(n=10, seed=2)
    # At least some payment_ids should differ
    ids_a = {e.payment_id for e in events_a}
    ids_b = {e.payment_id for e in events_b}
    assert ids_a != ids_b


def test_events_are_sorted_by_timestamp():
    events = generate_dataset(n=50, seed=42)
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


def test_has_multiple_failure_codes():
    events = generate_dataset(n=100, seed=42)
    failure_codes = {e.failure_code for e in events}
    # Should have at least 4 different failure codes
    assert len(failure_codes) >= 4


def test_has_multiple_payment_methods():
    events = generate_dataset(n=100, seed=42)
    methods = {e.payment_method for e in events}
    assert len(methods) >= 2


def test_card_events_have_network_and_issuer():
    events = generate_dataset(n=100, seed=42)
    card_events = [e for e in events if e.payment_method == "card"]
    assert len(card_events) > 0
    for e in card_events:
        assert e.card_network is not None
        assert e.issuer_bank is not None


def test_non_card_events_have_no_card_network():
    events = generate_dataset(n=100, seed=42)
    upi_events = [e for e in events if e.payment_method == "upi"]
    for e in upi_events:
        assert e.card_network is None


def test_amounts_are_positive():
    events = generate_dataset(n=100, seed=42)
    for e in events:
        assert e.amount > 0


def test_multiple_customers_share_failures():
    """Some customers should appear more than once (repeat failures)."""
    events = generate_dataset(n=50, seed=42)
    from collections import Counter
    customer_counts = Counter(e.customer_id for e in events)
    repeat_customers = [c for c, n in customer_counts.items() if n > 1]
    assert len(repeat_customers) > 0
