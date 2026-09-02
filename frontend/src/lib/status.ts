import type { DisplayStatus, QueueItem, TimelineEvent } from "../types/recovery";

const CUSTOMER_ACTIONS = new Set([
  "payment_reminder",
  "payment_method_update_request",
  "request_new_payment_method",
  "notify_customer",
]);

/**
 * Permanent failure codes that can never be retried without customer action.
 * These are non-recoverable by the automated workflow.
 */
const NON_RECOVERABLE_CODES = new Set([
  "invalid_card",
  "expired_card",
  "lost_card",
  "stolen_card",
  "do_not_honor",
  "permanent_failure",
  "card_blocked",
  "account_closed",
]);

/** True if the payment failure is permanently non-recoverable by automation. */
export function isNonRecoverableFailure(item: QueueItem): boolean {
  const code = (item.failure_type || "").toLowerCase();
  const reason = (item.failure_reason || "").toLowerCase();
  return (
    NON_RECOVERABLE_CODES.has(code) ||
    reason.includes("invalid card") ||
    reason.includes("expired card")
  );
}

export function displayStatus(item: QueueItem): DisplayStatus {
  const status = item.status.toLowerCase();
  if (status === "recovered") return "recovered";
  if (status === "escalated") return "escalated";
  if (status === "failed" || status === "closed") return "stopped";

  if (item.can_advance && (item.workflow_started || item.attempt_count > 0)) {
    return "recovering";
  }

  const action = item.latest_action || "";
  const outcome = item.latest_outcome || "";
  if (
    !item.can_advance &&
    (outcome === "no_response" ||
      outcome === "customer_response" ||
      CUSTOMER_ACTIONS.has(action))
  ) {
    return "awaiting_customer";
  }

  if (item.workflow_started || item.attempt_count > 0) return "recovering";
  return "open";
}

export function statusLabel(status: DisplayStatus): string {
  switch (status) {
    case "open":
      return "Open";
    case "recovering":
      return "Recovering";
    case "awaiting_customer":
      return "Awaiting customer";
    case "recovered":
      return "Recovered";
    case "escalated":
      return "Escalated";
    case "stopped":
      return "Stopped";
  }
}

export function isTerminalStatus(item: QueueItem): boolean {
  const status = displayStatus(item);
  return status === "recovered" || status === "escalated" || status === "stopped";
}

export interface ScenarioCopy {
  label: string;
  description: string;
}

export function scenarioFromState(item: QueueItem, events: TimelineEvent[]): ScenarioCopy | null {
  const hasAdaptive = events.some((event) => event.event_type === "adaptive_transition");
  const status = displayStatus(item);
  const nonRecoverable = isNonRecoverableFailure(item);

  // Permanent failure — pre-run or post-escalation
  if (nonRecoverable && !item.workflow_started) {
    return {
      label: "Permanent failure",
      description: "This payment method cannot be recovered by automated retry. Manual resolution or customer action required.",
    };
  }

  if (status === "escalated") {
    return {
      label: "Non-recoverable · Escalated",
      description: "The automated workflow confirmed this payment method is permanently invalid. No further retries will be made.",
    };
  }

  if (status === "recovered" && hasAdaptive) {
    return {
      label: "Adaptive recovery · Successful",
      description: "Strategy changed after the first attempt did not recover the payment. The adjusted approach succeeded.",
    };
  }
  if (status === "recovered") {
    return {
      label: "Successful recovery",
      description: "Payment recovered after a transient failure. Single strategy was sufficient.",
    };
  }

  if (hasAdaptive) {
    return {
      label: "Adaptive recovery · In progress",
      description: "The planner changed strategy based on the previous outcome. The next action is queued.",
    };
  }

  if (status === "recovering" && item.attempt_count > 0) {
    return {
      label: "Recovery in progress",
      description: "Workflow started. Awaiting customer response or retry window before the next cycle.",
    };
  }

  return null;
}
