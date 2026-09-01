import type { DisplayStatus, QueueItem, TimelineEvent } from "../types/recovery";

const CUSTOMER_ACTIONS = new Set([
  "payment_reminder",
  "payment_method_update_request",
  "request_new_payment_method",
  "notify_customer",
]);

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

  if (status === "recovered" && hasAdaptive) {
    return {
      label: "Adaptive recovery",
      description: "Strategy changed after the first recovery attempt failed.",
    };
  }
  if (status === "recovered") {
    return {
      label: "Successful recovery",
      description: "Recovered after a transient payment failure.",
    };
  }
  if (status === "escalated") {
    return {
      label: "Escalated",
      description: "Automated recovery stopped because the payment method is non-recoverable.",
    };
  }
  if (hasAdaptive) {
    return {
      label: "Adaptive recovery",
      description: "The planner changed strategy after observing the previous outcome.",
    };
  }
  return null;
}
