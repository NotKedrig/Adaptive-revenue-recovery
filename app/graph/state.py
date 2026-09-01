from typing import Annotated, Sequence, TypedDict
import operator

class RecoveryState(TypedDict, total=False):
    """
    LangGraph state for the AI Revenue Recovery System POC.
    """
    # A list of dictionaries representing the conversation or event history
    messages: Annotated[Sequence[dict], operator.add]
    
    # The string identifier of the next agent to route to
    next_agent: str
    
    # Payment / Customer Context
    payment_id: str
    merchant_id: str
    customer_id: str
    amount: float
    currency: str
    failure_code: str
    failure_reason: str
    payment_method: str
    card_network: str
    issuer_bank: str
    
    # Recovery State & Diagnosis
    diagnosis: dict               # Failure classification + root cause
    diagnosis_confidence: float   # Confidence score of the diagnosis
    recovery_strategy: dict       # Current active recovery plan/strategy
    recovery_actions: list[dict]  # History of attempted actions
    current_action: dict          # Action currently being executed
    
    # Routing & Signals
    outcome_signal: str           # "recovered", "partial", "failed", "no_response"
    escalation_level: int         # e.g., 0=initial, 1=retry, 2=notification, 3=human
    case_status: str              # "open", "recovered", "failed", "escalated"
    
    # Safety & Compliance
    safety_cleared: bool
    safety_flags: list[str]
    
    # Strategy & Action (Phase 3 & 4)
    strategy: dict
    approved_strategy: dict
    policy_decision: dict
    action_request: dict
    action_result: dict
    
    # Phase 4: History & Accumulation
    strategy_history: Annotated[Sequence[dict], operator.add]
    action_history: Annotated[Sequence[dict], operator.add]
    outcome_history: Annotated[Sequence[dict], operator.add]
    latest_outcome: dict
    recovery_signal: str
    
    # Virtual Time for deterministic simulation
    simulated_time_hours: int

    # Workflow context
    attempt_count: int
    max_attempts: int
    runtime_metadata: Annotated[Sequence[dict], operator.add]
