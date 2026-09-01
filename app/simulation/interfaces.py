"""
app/simulation/interfaces.py — Revenue Recovery Simulation Interfaces (Phase 1).

Defines the core interfaces for the local simulation environment, allowing
the system to model realistic payment events, customer responses, and
recovery outcomes without requiring external APIs (e.g., Razorpay, SMS gateways).
"""

from typing import Any
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Payment Events
# ---------------------------------------------------------------------------

class SimulatedPaymentEvent(BaseModel):
    """
    Represents an incoming payment event (typically a failure or at-risk signal).
    """
    payment_id: str = Field(..., description="Unique payment identifier")
    customer_id: str = Field(..., description="Unique customer identifier")
    merchant_id: str = Field(..., description="Merchant identifier")
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field(default="INR", description="Currency code")
    
    payment_method: str = Field(..., description="e.g., card, upi, netbanking")
    card_network: str | None = Field(default=None, description="e.g., Visa, Mastercard")
    issuer_bank: str | None = Field(default=None, description="Issuing bank name")
    
    failure_code: str = Field(..., description="Raw failure code (e.g., 'insufficient_funds')")
    failure_reason: str = Field(..., description="Human-readable failure description")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ---------------------------------------------------------------------------
# Recovery Actions
# ---------------------------------------------------------------------------

class RecoveryActionRequest(BaseModel):
    """
    Represents an action taken by the recovery system (Action Agent).
    """
    case_id: str = Field(..., description="Recovery case identifier")
    action_type: str = Field(..., description="e.g., 'retry', 'notify_sms', 'notify_email'")
    payload: dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")


class RecoveryActionResponse(BaseModel):
    """
    Represents the immediate technical response to a recovery action.
    This does NOT represent the final outcome (e.g., whether the customer paid),
    but whether the action itself succeeded (e.g., SMS delivered, retry accepted).
    """
    success: bool = Field(..., description="Did the action execute successfully?")
    message: str = Field(..., description="Details of execution")
    provider_id: str | None = Field(default=None, description="Simulated gateway ID")


# ---------------------------------------------------------------------------
# Customer Responses & Outcomes
# ---------------------------------------------------------------------------

class SimulatedCustomerResponse(BaseModel):
    """
    Models the customer's reaction to a notification (e.g., opening a link, ignoring it).
    """
    case_id: str = Field(..., description="Recovery case identifier")
    customer_id: str = Field(..., description="Customer identifier")
    response_type: str = Field(..., description="e.g., 'clicked_link', 'ignored', 'replied_stop'")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class SimulatedPaymentOutcome(BaseModel):
    """
    The final or intermediate outcome of a recovery attempt (e.g., retry result).
    """
    case_id: str = Field(..., description="Recovery case identifier")
    attempt_id: str = Field(..., description="Identifier of the recovery attempt")
    status: str = Field(..., description="e.g., 'success', 'failed', 'partial'")
    amount_recovered: float = Field(default=0.0, description="Amount successfully recovered")
    error_code: str | None = Field(default=None, description="If failed, the new error code")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
