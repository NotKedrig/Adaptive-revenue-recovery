import { describe, expect, it } from "vitest";
import { looksLikeRawObject } from "./format";
import { humanizeAction, humanizeFailure, renderTimelineEvent } from "./events";
import { displayStatus, scenarioFromState } from "./status";
import type { QueueItem, TimelineEvent } from "../types/recovery";

function event(partial: Partial<TimelineEvent>): TimelineEvent {
  return {
    id: 1,
    event_type: "diagnosis",
    timestamp: "2026-01-01T00:00:00Z",
    actor: "diagnosis_agent",
    status: "info",
    summary: "",
    details: "",
    metadata: {},
    ...partial,
  };
}

function item(partial: Partial<QueueItem> = {}): QueueItem {
  return {
    case_id: "case_pay_nsf_002",
    payment_id: "pay_nsf_002",
    amount: 8200,
    currency: "INR",
    failure_type: "insufficient_funds",
    failure_reason: "Insufficient funds",
    status: "open",
    attempt_count: 0,
    max_attempts: 3,
    simulated_time_hours: 0,
    can_advance: true,
    workflow_started: false,
    ...partial,
  };
}

describe("event presentation", () => {
  it("humanizes failure codes and actions", () => {
    expect(humanizeFailure("insufficient_funds", "Insufficient funds")).toBe("Insufficient funds");
    expect(humanizeAction("immediate_retry")).toBe("Immediate payment retry");
    expect(humanizeAction("payment_reminder")).toBe("SMS reminder");
  });

  it("renders strategy and policy as operational copy", () => {
    const strategy = renderTimelineEvent(
      event({
        event_type: "strategy_proposed",
        metadata: {
          action: "payment_reminder",
          channel: "sms",
          retry_timing_hours: 48,
          rationale: "An immediate retry is unlikely to succeed.",
        },
      }),
    );
    expect(strategy.title).toContain("retry in 48h");
    expect(strategy.body).not.toContain("{");

    const blocked = renderTimelineEvent(
      event({
        event_type: "policy_decision",
        metadata: {
          allowed: false,
          reason: "Cannot execute automated retries for non-recoverable failures.",
          mutated_action: "request_new_payment_method",
        },
      }),
    );
    expect(blocked.title).toContain("Strategy modified");
    expect(blocked.body).toContain("non-recoverable");
  });

  it("renders diagnosis without raw objects", () => {
    const rendered = renderTimelineEvent(
      event({
        event_type: "diagnosis",
        metadata: {
          failure_category: "transient_customer",
          root_cause: "Customer account had insufficient funds at time of charge.",
          confidence: 0.7,
          evidence: ["Insufficient funds failure code"],
        },
      }),
    );
    expect(rendered.title).toBe("Transient customer failure");
    expect(rendered.body).not.toContain("{");
    expect(rendered.facts.some((fact) => fact.label === "Confidence")).toBe(true);
  });

  it("makes adaptive strategy changes explicit", () => {
    const rendered = renderTimelineEvent(
      event({
        event_type: "adaptive_transition",
        metadata: {
          previous_strategy_action: "immediate_retry",
          new_strategy_action: "delayed_retry",
          transition_reason: "Immediate retry failed for technical issue.",
        },
      }),
    );
    expect(rendered.previousStrategy).toBe("Immediate payment retry");
    expect(rendered.newStrategy).toBe("Delayed payment retry");
    expect(rendered.title).toBe("Adaptive planner · Strategy changed");
  });

  it("renders action and outcome without raw dictionaries", () => {
    const action = renderTimelineEvent(
      event({
        event_type: "action_executed",
        metadata: {
          action: "payment_reminder",
          result: { simulated_outcome: "reminder_sent", customer_response: null },
        },
      }),
    );
    expect(action.title).toContain("SMS reminder");
    expect(action.body).not.toContain("{");
    expect(action.body).not.toContain("simulated_outcome");

    const outcome = renderTimelineEvent(
      event({
        event_type: "recovery_signal",
        metadata: {
          signal_type: "transient_failure",
          context: { outcome: "recovery_failed", customer_response: null },
        },
      }),
    );
    expect(outcome.title).toBe("Recovery attempt unsuccessful");
    expect(outcome.body).not.toContain("{");
  });

  it("never treats dictionary strings as display copy", () => {
    expect(looksLikeRawObject("{'outcome': 'recovery_failed'}")).toBe(true);
    const rendered = renderTimelineEvent(
      event({
        event_type: "unknown_event",
        details: "{'outcome': 'recovery_failed'}",
        metadata: {},
      }),
    );
    expect(rendered.body).toBe("Event recorded by the recovery workflow.");
  });
});

describe("status and scenario", () => {
  it("maps recovered vs escalated distinctly", () => {
    expect(displayStatus(item({ status: "recovered" }))).toBe("recovered");
    expect(displayStatus(item({ status: "escalated" }))).toBe("escalated");
    expect(displayStatus(item({ workflow_started: true, attempt_count: 1 }))).toBe("recovering");
  });

  it("derives scenario copy from events, not case ids", () => {
    const adaptive = scenarioFromState(item({ status: "recovered" }), [
      event({ event_type: "adaptive_transition" }),
    ]);
    expect(adaptive?.label).toBe("Adaptive recovery · Successful");
    const escalated = scenarioFromState(item({ status: "escalated" }), []);
    expect(escalated?.label).toBe("Non-recoverable · Escalated");
  });
});
