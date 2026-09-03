import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecoveryQueuePage } from "./RecoveryQueuePage";
import * as api from "../services/api";
import type { BaselineComparison, Metrics, QueueItem, TimelineEvent } from "../types/recovery";

vi.mock("../services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/api")>();
  return {
    ...actual,
    getMetrics: vi.fn(),
    getQueue: vi.fn(),
    getRecovered: vi.fn(),
    getCase: vi.fn(),
    getCaseTimeline: vi.fn(),
    advanceRecovery: vi.fn(),
    loadDemoData: vi.fn(),
    getBaselineComparison: vi.fn(),
  };
});

const mocked = vi.mocked(api);

function metrics(partial: Partial<Metrics> = {}): Metrics {
  return {
    revenue_at_risk: 13699,
    revenue_recovered: 0,
    recovery_rate_percent: 0,
    as_of: "2026-09-01T00:00:00Z",
    ...partial,
  };
}

function item(partial: Partial<QueueItem>): QueueItem {
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

function timelineEvent(partial: Partial<TimelineEvent>): TimelineEvent {
  return {
    id: 1,
    event_type: "diagnosis",
    timestamp: "2026-09-01T00:00:00Z",
    actor: "diagnosis_agent",
    status: "info",
    summary: "",
    details: "",
    metadata: {},
    ...partial,
  };
}

const nsf = item({});
const tech = item({
  case_id: "case_pay_tech_001",
  payment_id: "pay_tech_001",
  amount: 4500,
  failure_type: "bank_timeout",
  failure_reason: "Bank timeout",
});
const perm = item({
  case_id: "case_pay_perm_003",
  payment_id: "pay_perm_003",
  amount: 999,
  failure_type: "invalid_card",
  failure_reason: "Invalid card",
});

describe("RecoveryQueuePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    mocked.getMetrics.mockResolvedValue(metrics());
    mocked.getQueue.mockResolvedValue([nsf, tech, perm]);
    mocked.getRecovered.mockResolvedValue([]);
    mocked.getCase.mockImplementation(async (caseId) => {
      return [nsf, tech, perm].find((row) => row.case_id === caseId) ?? nsf;
    });
    mocked.getCaseTimeline.mockResolvedValue([]);
    mocked.advanceRecovery.mockResolvedValue({
      case_id: nsf.case_id,
      status: "open",
      can_advance: true,
      simulated_time_hours: 48,
      attempt_count: 1,
    });
    mocked.loadDemoData.mockResolvedValue({
      status: "success",
      message: "Demo data loaded. 3 recovery scenarios ready.",
      case_ids: [nsf.case_id, tech.case_id, perm.case_id],
    });
    const mockBaseline: BaselineComparison = {
      case_count: 40,
      total_revenue_at_risk: 409754.8,
      naive: { recovered_revenue: 145460.02, recovery_rate_percent: 35.5 },
      adaptive: { recovered_revenue: 195499.98, recovery_rate_percent: 47.71 },
      improvement_percentage_points: 12.21,
      additional_revenue_recovered: 50039.96,
      evaluation_seed: 777,
      external_llm_calls: false,
      simulation_mode: "deterministic",
    };
    mocked.getBaselineComparison.mockResolvedValue(mockBaseline);
  });

  it("renders the three primary metrics and the live queue", async () => {
    render(<RecoveryQueuePage />);

    expect(await screen.findByText("Revenue at risk")).toBeTruthy();
    expect(screen.getByText("₹13,699")).toBeTruthy();
    expect(screen.getByText("Revenue recovered")).toBeTruthy();
    expect(screen.getByText("Recovery rate")).toBeTruthy();
    expect(screen.getByText("0.0%")).toBeTruthy();

    expect(screen.getByRole("tab", { name: /Live Queue/ })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /Recovered/ })).toBeTruthy();
    expect(screen.getByText("pay_nsf_002")).toBeTruthy();
    expect(screen.getByText("pay_tech_001")).toBeTruthy();
    expect(screen.getByText("pay_perm_003")).toBeTruthy();
    expect(screen.getAllByText("₹8,200").length).toBeGreaterThan(0);
    expect(screen.queryByText("$")).toBeNull();
  });

  it("shows an empty recovered tab until cases are recovered", async () => {
    render(<RecoveryQueuePage />);
    await screen.findByText("pay_nsf_002");

    await userEvent.click(screen.getByRole("tab", { name: /Recovered/ }));
    expect(screen.getByText("No recovered cases yet.")).toBeTruthy();
    expect(screen.queryByText("pay_nsf_002")).toBeNull();
  });

  it("opens a case workspace and runs recovery through the backend API", async () => {
    const recovering = item({
      status: "open",
      workflow_started: true,
      attempt_count: 1,
      latest_action: "payment_reminder",
      simulated_time_hours: 48,
      can_advance: true,
    });
    const events = [
      timelineEvent({
        id: 1,
        event_type: "diagnosis",
        metadata: {
          failure_category: "transient_customer",
          root_cause: "Customer account had insufficient funds at time of charge.",
          confidence: 0.95,
          evidence: ["Insufficient funds failure code"],
        },
      }),
      timelineEvent({
        id: 2,
        event_type: "strategy_proposed",
        metadata: {
          action: "payment_reminder",
          channel: "sms",
          retry_timing_hours: 48,
          rationale: "An immediate retry is unlikely to succeed.",
        },
      }),
      timelineEvent({
        id: 3,
        event_type: "policy_decision",
        metadata: { allowed: true, reason: "Strategy passed all safety checks." },
      }),
      timelineEvent({
        id: 4,
        event_type: "action_executed",
        metadata: {
          action: "payment_reminder",
          result: { simulated_outcome: "reminder_sent" },
        },
      }),
      timelineEvent({
        id: 5,
        event_type: "recovery_signal",
        metadata: { signal_type: "no_response", context: { outcome: "reminder_sent" } },
      }),
    ];

    mocked.getCase.mockResolvedValue(recovering);
    mocked.getCaseTimeline.mockResolvedValue(events);

    render(<RecoveryQueuePage />);
    await screen.findByText("pay_nsf_002");
    await userEvent.click(screen.getByRole("button", { name: /Open recovery case pay_nsf_002/ }));

    const workspace = await screen.findByRole("dialog", { name: "pay_nsf_002" });
    expect(within(workspace).getAllByText("₹8,200").length).toBeGreaterThan(0);
    expect(within(workspace).getAllByText("Insufficient funds").length).toBeGreaterThan(0);
    expect(within(workspace).getByText("Diagnosis agent")).toBeTruthy();
    expect(within(workspace).getByText("Strategy engine")).toBeTruthy();
    expect(within(workspace).getByText("Policy guard")).toBeTruthy();
    expect(within(workspace).getByText("Outcome detector")).toBeTruthy();
    expect(within(workspace).getAllByText(/SMS reminder/).length).toBeGreaterThan(0);
    expect(within(workspace).queryByText("{")).toBeNull();

    const recovered = item({
      status: "recovered",
      workflow_started: true,
      attempt_count: 2,
      recovered_amount: 8200,
      can_advance: false,
      simulated_time_hours: 72,
    });
    mocked.advanceRecovery.mockResolvedValue({
      case_id: nsf.case_id,
      status: "recovered",
      can_advance: false,
      simulated_time_hours: 72,
      attempt_count: 2,
    });
    mocked.getCase.mockResolvedValue(recovered);
    mocked.getCaseTimeline.mockResolvedValue([
      ...events,
      timelineEvent({
        id: 6,
        event_type: "adaptive_transition",
        metadata: {
          previous_strategy_action: "payment_reminder",
          new_strategy_action: "delayed_retry",
          transition_reason: "No response via SMS. Falling back to delayed background retry.",
        },
      }),
    ]);
    mocked.getQueue.mockResolvedValue([tech, perm]);
    mocked.getRecovered.mockResolvedValue([recovered]);
    mocked.getMetrics.mockResolvedValue(
      metrics({ revenue_at_risk: 5499, revenue_recovered: 8200, recovery_rate_percent: 59.9 }),
    );

    await userEvent.click(within(workspace).getByRole("button", { name: /Advance recovery|Run recovery/ }));

    await waitFor(() => {
      expect(mocked.advanceRecovery).toHaveBeenCalledWith("case_pay_nsf_002");
    });
    expect(await screen.findByText("Adaptive planner · Strategy changed")).toBeTruthy();
    expect(screen.getByText("Previous strategy")).toBeTruthy();
    expect(screen.getByText("New strategy")).toBeTruthy();
    expect(screen.getByText("Recovered. Automated recovery is complete.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Advance recovery|Run recovery/ })).toBeNull();
  });

  it("does not fabricate recovery actions in the frontend", async () => {
    render(<RecoveryQueuePage />);
    await screen.findByText("pay_nsf_002");
    expect(mocked.advanceRecovery).not.toHaveBeenCalled();
    expect(mocked.getQueue).toHaveBeenCalled();
    expect(mocked.getMetrics).toHaveBeenCalled();
  });

  it("shows non-recoverable notice for invalid_card case and no recovery button", async () => {
    // Permanent failure case: invalid_card, workflow not started
    const permCase = item({
      case_id: "case_pay_perm_003",
      payment_id: "pay_perm_003",
      amount: 999,
      failure_type: "invalid_card",
      failure_reason: "Invalid card",
      status: "open",
      can_advance: true,
      workflow_started: false,
    });
    mocked.getCase.mockResolvedValue(permCase);
    mocked.getCaseTimeline.mockResolvedValue([]);

    render(<RecoveryQueuePage />);
    await screen.findByText("pay_perm_003");

    // The queue row should show a non-recoverable label
    expect(screen.getByText("Non-recoverable · Escalation required")).toBeTruthy();

    // Open the case workspace
    await userEvent.click(screen.getByRole("button", { name: /Open recovery case pay_perm_003/ }));
    const workspace = await screen.findByRole("dialog", { name: "pay_perm_003" });

    // Should show the non-recoverable notice, NOT a Run/Advance recovery button
    expect(within(workspace).getByText("Non-recoverable failure")).toBeTruthy();
    expect(within(workspace).queryByRole("button", { name: /Run recovery|Advance recovery/ })).toBeNull();

    // No API call should have been made for advance
    expect(mocked.advanceRecovery).not.toHaveBeenCalled();
  });

  it("shows escalated note for already-escalated permanent failure and no recovery button", async () => {
    const escalatedCase = item({
      case_id: "case_pay_perm_003",
      payment_id: "pay_perm_003",
      amount: 999,
      failure_type: "invalid_card",
      failure_reason: "Invalid card",
      status: "escalated",
      can_advance: false,
      workflow_started: true,
      attempt_count: 1,
    });
    mocked.getCase.mockResolvedValue(escalatedCase);
    mocked.getCaseTimeline.mockResolvedValue([
      timelineEvent({
        id: 1,
        event_type: "escalation",
        metadata: {},
      }),
    ]);

    render(<RecoveryQueuePage />);
    await screen.findByText("pay_perm_003");

    await userEvent.click(screen.getByRole("button", { name: /Open recovery case pay_perm_003/ }));
    const workspace = await screen.findByRole("dialog", { name: "pay_perm_003" });

    // Should show escalated terminal note
    expect(
      within(workspace).getByText(/Escalated — non-recoverable/i),
    ).toBeTruthy();
    // No recovery button
    expect(within(workspace).queryByRole("button", { name: /Run recovery|Advance recovery/ })).toBeNull();
  });

});
