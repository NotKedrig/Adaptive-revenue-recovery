"""
app/agents/schemas.py — Core Pydantic models for Strategy, Policy, and Actions.
"""
from typing import Optional
from pydantic import BaseModel, Field


class RecoveryStrategy(BaseModel):
    """The planner's recommended strategy for a given failure."""
    action: str = Field(
        ...,
        description="The recommended action: 'immediate_retry', 'delayed_retry', 'payment_method_update_request', 'payment_reminder', 'escalate_to_human', 'stop_recovery'"
    )
    channel: Optional[str] = Field(
        default=None,
        description="The communication channel to use, e.g., 'email', 'sms', 'whatsapp', or None if internal."
    )
    retry_timing_hours: int = Field(
        default=0,
        description="Hours to wait before executing the action (0 for immediate)."
    )
    maximum_attempts: int = Field(
        default=3,
        description="The maximum number of times this specific strategy can be attempted."
    )
    escalation_condition: str = Field(
        default="max_attempts_reached",
        description="The condition under which this case should be escalated."
    )
    expected_outcome: str = Field(
        default="unknown",
        description="The anticipated outcome of this strategy."
    )
    rationale: str = Field(
        default="",
        description="The reasoning behind selecting this strategy."
    )


class PolicyDecision(BaseModel):
    """The outcome of the policy guard layer."""
    allowed: bool = Field(
        ...,
        description="Whether the strategy is allowed to proceed."
    )
    reason: str = Field(
        ...,
        description="The reason for allowing or blocking the strategy."
    )
    mutated_action: Optional[str] = Field(
        default=None,
        description="If blocked, the action is mutated to a safe default (e.g., 'stop_recovery')."
    )


class RecoveryOutcome(BaseModel):
    """The detector's interpretation of a simulated action result."""
    outcome_category: str = Field(
        ...,
        description="e.g., 'recovered', 'failed_transient', 'failed_permanent', 'customer_responded', 'customer_did_not_respond', 'retry_exhausted'"
    )
    is_terminal: bool = Field(
        default=False,
        description="True if this outcome terminates the recovery loop."
    )
    escalate_to_human: bool = Field(
        default=False,
        description="True if the terminal outcome requires human escalation rather than simply stopping."
    )
    details: str = Field(
        default="",
        description="Additional context about the outcome."
    )


class RecoverySignal(BaseModel):
    """Explicit signals driving future strategy decisions."""
    signal_type: str
    timestamp: str
    source_action: str
    context: dict = Field(default_factory=dict)


class RecoveryActionRequest(BaseModel):
    """The structured payload sent to the execution/simulation engine."""
    payment_id: str
    action_type: str
    channel: Optional[str] = None
    delay_hours: int = 0
    idempotency_key: str = ""


class RecoveryActionResult(BaseModel):
    """The result returned from the execution/simulation engine."""
    success: bool
    simulated_outcome: str
    customer_response: Optional[str] = None
    timestamp: str
    metadata: dict = Field(default_factory=dict)
