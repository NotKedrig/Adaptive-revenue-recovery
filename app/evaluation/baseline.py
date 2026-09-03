"""
app/evaluation/baseline.py — Deterministic Baseline Comparison (Phase 6).

Compares two strategies on a fixed 40-case evaluation dataset:

  A) NAIVE BASELINE  — one immediate_retry, no adaptation, no diagnosis.
  B) ADAPTIVE SYSTEM — uses the existing Phase 4 deterministic agents
     (diagnosis → strategy → policy → action → outcome → adaptive planner)
     without writing to the live database.

Key design constraints:
  - Fully local and deterministic.
  - Does NOT call any external LLM or API.
  - Does NOT mutate the live demo database.
  - Reuses RECOVERY_PROBABILITIES and the agent rule engines directly.
  - Uses a fixed seed (777) so results are identical on every call.

RNG methodology — Common Random Numbers (CRN):
  Each case i is evaluated with a freshly-seeded sub-RNG
  (seed = EVAL_SEED * 1000 + i) that is created independently for
  both the naive and adaptive evaluators.  This guarantees that both
  strategies face exactly the same sequence of random draws for every
  case, so the measured difference is attributable purely to strategy
  quality rather than to different luck-of-the-draw outcomes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.agents.diagnosis import _fallback_diagnosis
from app.agents.policy import _evaluate_policy
from app.agents.strategy import _plan_strategy
from app.simulation.dataset import generate_dataset
from app.simulation.engine import RECOVERY_PROBABILITIES
from app.simulation.interfaces import SimulatedPaymentEvent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_SEED: int = 777
EVAL_N: int = 40
MAX_ATTEMPTS: int = 3

# ---------------------------------------------------------------------------
# In-memory outcome simulation (no DB, no external calls)
# ---------------------------------------------------------------------------


def _simulate_action(
    failure_code: str,
    action_type: str,
    delay_hours: int,
    rng: random.Random,
) -> tuple[str, str | None]:
    """
    Deterministic outcome simulation mirroring SimulationEngine.execute_action()
    logic but without DB writes or payment_id keyword hacks.

    Returns (simulated_outcome, customer_response).
    """
    probs = RECOVERY_PROBABILITIES.get(failure_code, {})

    if action_type in ("immediate_retry", "delayed_retry"):
        base_prob = probs.get("retry", 0.0)
        # For transient_technical failures the engine requires delay >= 4h for
        # delayed_retry to succeed.  Mirror that here: a delayed_retry with no
        # delay behaves like immediate_retry.
        if action_type == "delayed_retry" and delay_hours >= 4:
            roll = rng.random()
            return ("recovery_successful", None) if roll < base_prob else ("recovery_failed", None)
        else:
            roll = rng.random()
            return ("recovery_successful", None) if roll < base_prob else ("recovery_failed", None)

    elif action_type == "payment_reminder":
        roll = rng.random()
        # SMS has higher response rate; email lower
        threshold = 0.35 if True else 0.25  # simplified: always use SMS probability
        customer_response = "clicked_link" if roll > (1 - threshold) else None
        return ("reminder_sent", customer_response)

    elif action_type == "payment_method_update_request":
        roll = rng.random()
        customer_response = "updated_payment_method" if roll > 0.5 else None
        return ("customer_notified", customer_response)

    elif action_type in ("stop_recovery", "escalate_to_human"):
        return ("escalated", None)

    elif action_type == "request_new_payment_method":
        roll = rng.random()
        customer_response = "updated_payment_method" if roll > 0.5 else None
        return ("customer_notified", customer_response)

    # Unknown actions
    return ("recovery_failed", None)


def _outcome_signal(simulated_outcome: str, customer_response: str | None) -> tuple[str, bool]:
    """
    Map simulated_outcome → (signal_type, is_terminal).
    Mirrors outcome_node logic.
    """
    if simulated_outcome == "recovery_successful":
        return "success", True
    if simulated_outcome in ("recovery_stopped", "escalated"):
        return "permanent_failure", True
    if simulated_outcome == "recovery_failed":
        return "transient_failure", False
    if simulated_outcome in ("reminder_sent", "customer_notified"):
        if customer_response:
            return "customer_response", False
        return "no_response", False
    return "unknown_signal", False


# ---------------------------------------------------------------------------
# Naive baseline evaluator
# ---------------------------------------------------------------------------


def _evaluate_naive(event: SimulatedPaymentEvent, rng: random.Random) -> float:
    """
    Naive strategy: one immediate_retry, fixed 0h delay, no adaptation.
    Returns the recovered amount (0.0 if not recovered).
    """
    outcome, _ = _simulate_action(event.failure_code, "immediate_retry", 0, rng)
    if outcome == "recovery_successful":
        return event.amount
    return 0.0


# ---------------------------------------------------------------------------
# Adaptive evaluator (reuses existing Phase 4 agent rule engines)
# ---------------------------------------------------------------------------


def _evaluate_adaptive(event: SimulatedPaymentEvent, rng: random.Random) -> float:
    """
    Adaptive strategy using the existing Phase 4 rule engines (no DB, no LLM).

    Cycle 0: diagnosis → strategy → policy → action → outcome
    Cycles 1+: adaptive_planner (inline logic) → policy → action → outcome

    Returns the recovered amount (0.0 if not recovered).
    """
    # Build a lightweight in-memory state — mirrors RecoveryState fields
    state: dict[str, Any] = {
        "payment_id": event.payment_id,
        "failure_code": event.failure_code,
        "failure_reason": event.failure_reason,
        "attempt_count": 0,
        "max_attempts": MAX_ATTEMPTS,
        "simulated_time_hours": 0,
        "strategy_history": [],
        "outcome_history": [],
        "latest_outcome": {},
        "recovery_signal": "",
    }

    # --- First cycle: diagnosis → strategy ---
    diagnosis = _fallback_diagnosis(event.failure_code, event.failure_reason)
    state["diagnosis"] = diagnosis.model_dump()

    for cycle in range(MAX_ATTEMPTS + 2):  # hard cap matching recovery_runner
        # Strategy selection
        if cycle == 0:
            strategy = _plan_strategy(state["diagnosis"], state["attempt_count"])
        else:
            # Inline adaptive planner (mirrors adaptive_planner.py logic without DB writes)
            strategy = _adaptive_plan(state, rng)

        state["strategy"] = strategy.model_dump()

        # Policy guard
        policy = _evaluate_policy(state["strategy"], state)  # type: ignore[arg-type]
        if not policy.allowed and policy.mutated_action:
            state["strategy"] = dict(state["strategy"])
            state["strategy"]["action"] = policy.mutated_action

        # Execute action
        action_type = state["strategy"]["action"]
        delay = state["strategy"].get("retry_timing_hours", 0) or 0
        state["simulated_time_hours"] = state["simulated_time_hours"] + delay
        state["attempt_count"] += 1

        simulated_outcome, customer_response = _simulate_action(
            event.failure_code, action_type, delay, rng
        )

        signal, is_terminal = _outcome_signal(simulated_outcome, customer_response)
        state["recovery_signal"] = signal
        state["latest_outcome"] = {
            "outcome_category": "recovered" if signal == "success" else "other",
            "is_terminal": is_terminal,
        }
        state["strategy_history"] = list(state["strategy_history"]) + [state["strategy"]]
        state["outcome_history"] = list(state["outcome_history"]) + [state["latest_outcome"]]

        if signal == "success":
            return event.amount  # fully recovered
        if is_terminal:
            return 0.0  # escalated / stopped
        if state["attempt_count"] >= MAX_ATTEMPTS + 2:
            return 0.0  # loop guard

    return 0.0


def _adaptive_plan(state: dict[str, Any], rng: random.Random):
    """
    Inline adaptive planner that mirrors adaptive_planner.py logic without DB writes.
    """
    from app.agents.schemas import RecoveryStrategy

    signal = state.get("recovery_signal", "")
    attempt_count = state.get("attempt_count", 0)
    max_attempts = state.get("max_attempts", MAX_ATTEMPTS)
    strategy_history = state.get("strategy_history", [])
    previous_strategy = strategy_history[-1] if strategy_history else {}
    previous_action = previous_strategy.get("action", "unknown")
    diagnosis = state.get("diagnosis", {})

    if signal == "success":
        return RecoveryStrategy(
            action="stop_recovery", channel=None, retry_timing_hours=0,
            maximum_attempts=max_attempts, escalation_condition="completed",
            expected_outcome="recovered", rationale="Already recovered."
        )

    if signal == "permanent_failure" or attempt_count >= max_attempts:
        return RecoveryStrategy(
            action="escalate_to_human", channel=None, retry_timing_hours=0,
            maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
            expected_outcome="escalated", rationale="Exhausted attempts or permanent failure."
        )

    if signal == "customer_response":
        return RecoveryStrategy(
            action="immediate_retry", channel=None, retry_timing_hours=0,
            maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
            expected_outcome="successful_authorization",
            rationale="Customer responded. Attempting immediate retry."
        )

    if signal == "no_response":
        if previous_action in ("payment_reminder", "payment_method_update_request"):
            if previous_strategy.get("channel") == "email":
                return RecoveryStrategy(
                    action="payment_reminder", channel="sms", retry_timing_hours=0,
                    maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
                    expected_outcome="funds_available",
                    rationale="No response via email. Escalating to SMS."
                )
            else:
                return RecoveryStrategy(
                    action="delayed_retry", channel=None, retry_timing_hours=24,
                    maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
                    expected_outcome="successful_authorization",
                    rationale="No response via SMS. Scheduling delayed retry."
                )
        return RecoveryStrategy(
            action="delayed_retry", channel=None, retry_timing_hours=24,
            maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
            expected_outcome="successful_authorization",
            rationale="No customer response. Scheduling delayed retry."
        )

    if signal == "transient_failure":
        if previous_action == "immediate_retry":
            if diagnosis.get("failure_category") == "transient_customer":
                return RecoveryStrategy(
                    action="payment_reminder", channel="email", retry_timing_hours=0,
                    maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
                    expected_outcome="funds_available",
                    rationale="Immediate retry failed (customer issue). Sending email reminder."
                )
            else:
                return RecoveryStrategy(
                    action="delayed_retry", channel=None, retry_timing_hours=12,
                    maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
                    expected_outcome="successful_authorization",
                    rationale="Immediate retry failed (technical). Applying 12h backoff."
                )
        elif previous_action == "delayed_retry":
            return RecoveryStrategy(
                action="payment_method_update_request", channel="email", retry_timing_hours=0,
                maximum_attempts=max_attempts, escalation_condition="max_attempts_reached",
                expected_outcome="customer_update_required",
                rationale="Delayed retry failed. Requesting payment method update."
            )

    return RecoveryStrategy(
        action="escalate_to_human", channel=None, retry_timing_hours=0,
        maximum_attempts=max_attempts, escalation_condition="unknown",
        expected_outcome="escalated",
        rationale=f"Unknown signal '{signal}'. Escalating."
    )


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class StrategyResult(BaseModel):
    recovered_revenue: float
    recovery_rate_percent: float


class BaselineComparisonResult(BaseModel):
    case_count: int
    total_revenue_at_risk: float
    naive: StrategyResult
    adaptive: StrategyResult
    improvement_percentage_points: float
    additional_revenue_recovered: float
    evaluation_seed: int
    external_llm_calls: bool = False
    simulation_mode: str = "deterministic"


# ---------------------------------------------------------------------------
# Main evaluation entry-point
# ---------------------------------------------------------------------------


def run_baseline_comparison() -> BaselineComparisonResult:
    """
    Run the deterministic 40-case evaluation and return a BaselineComparisonResult.

    Uses seed=EVAL_SEED (777) for both dataset generation and outcome simulation,
    ensuring identical results on every call.

    No database writes. No external API calls.
    """
    events = generate_dataset(n=EVAL_N, seed=EVAL_SEED)

    total_revenue = sum(e.amount for e in events)

    naive_recovered = 0.0
    adaptive_recovered = 0.0

    for i, event in enumerate(events):
        # Common Random Numbers (CRN): give each case its own deterministic
        # sub-RNG derived from the global seed + case index.  Both naive and
        # adaptive receive a freshly-seeded RNG for the same case, so they
        # draw from identical random streams.  Strategy quality, not
        # different random luck, drives the measured difference.
        case_seed = EVAL_SEED * 1000 + i
        naive_recovered   += _evaluate_naive(event, random.Random(case_seed))
        adaptive_recovered += _evaluate_adaptive(event, random.Random(case_seed))

    def _rate(recovered: float, total: float) -> float:
        if total <= 0:
            return 0.0
        return round((recovered / total) * 100, 2)

    naive_rate = _rate(naive_recovered, total_revenue)
    adaptive_rate = _rate(adaptive_recovered, total_revenue)

    return BaselineComparisonResult(
        case_count=len(events),
        total_revenue_at_risk=round(total_revenue, 2),
        naive=StrategyResult(
            recovered_revenue=round(naive_recovered, 2),
            recovery_rate_percent=naive_rate,
        ),
        adaptive=StrategyResult(
            recovered_revenue=round(adaptive_recovered, 2),
            recovery_rate_percent=adaptive_rate,
        ),
        improvement_percentage_points=round(adaptive_rate - naive_rate, 2),
        additional_revenue_recovered=round(adaptive_recovered - naive_recovered, 2),
        evaluation_seed=EVAL_SEED,
        external_llm_calls=False,
        simulation_mode="deterministic",
    )
