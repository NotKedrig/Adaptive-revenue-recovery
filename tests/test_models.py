"""
tests/test_models.py - Tests for the new Revenue Recovery DB models.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

from app.db.state.models import Base, Customer, Payment, RecoveryCase

@pytest.fixture(scope="module")
def engine():
    # Use in-memory SQLite for fast testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

def test_create_customer_and_payment(session):
    # 1. Create a Customer
    customer = Customer(
        customer_id="cust_123",
        merchant_id="merch_abc",
        name="John Doe",
        email="john@example.com"
    )
    session.add(customer)
    session.commit()
    
    assert customer.id is not None
    
    # 2. Create a Payment
    payment = Payment(
        payment_id="pay_999",
        customer_id=customer.customer_id,
        amount=Decimal("1500.50"),
        currency="INR",
        payment_method="card",
        failure_code="insufficient_funds"
    )
    session.add(payment)
    session.commit()
    
    assert payment.id is not None
    assert payment.amount == Decimal("1500.50")
    
    # 3. Verify relationships
    assert len(customer.payments) == 1
    assert customer.payments[0].payment_id == "pay_999"

def test_create_recovery_case(session):
    # Create the prerequisite Customer and Payment
    customer = Customer(customer_id="cust_456", merchant_id="merch_xyz")
    payment = Payment(payment_id="pay_888", customer_id="cust_456", amount=Decimal("500.00"))
    session.add_all([customer, payment])
    session.commit()
    
    # 4. Create RecoveryCase
    case = RecoveryCase(
        case_id="case_001",
        payment_id=payment.payment_id,
        status="open",
        escalation_level=0
    )
    session.add(case)
    session.commit()
    
    assert case.id is not None
    assert case.payment.amount == Decimal("500.00")
