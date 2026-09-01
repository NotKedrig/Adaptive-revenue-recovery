import { asNumber, asRecord, asString, asStringList } from "./format";
import type { TimelineEvent } from "../types/recovery";

export function humanizeFailure(code: string | null | undefined, reason?: string | null): string {
  const source = (reason || code || "Unknown failure").replace(/_/g, " ");
  if (!source) return "Unknown failure";
  return source.charAt(0).toUpperCase() + source.slice(1);
}

export function humanizeAction(action: string | null | undefined): string {
  switch (action) {
    case "immediate_retry":
      return "Immediate payment retry";
    case "delayed_retry":
      return "Delayed payment retry";
    case "payment_reminder":
      return "SMS reminder";
    case "request_new_payment_method":
    case "payment_method_update_request":
      return "Payment method update request";
    case "escalate_to_human":
      return "Escalate to operations";
    case "stop_recovery":
      return "Stop recovery";
    case "notify_customer":
      return "Customer notification";
    default:
      return action ? action.replace(/_/g, " ") : "Recovery action";
  }
}

export function humanizeChannel(channel: string | null | undefined): string | null {
  if (!channel) return null;
  if (channel === "sms") return "SMS";
  return channel.charAt(0).toUpperCase() + channel.slice(1);
}

export function humanizeOutcome(signal: string | null | undefined, simulated?: string | null): string {
  const value = simulated || signal || "";
  switch (value) {
    case "success":
    case "recovery_successful":
      return "Payment recovered";
    case "transient_failure":
    case "recovery_failed":
      return "Recovery attempt unsuccessful";
    case "no_response":
    case "reminder_sent":
      return "Customer did not respond";
    case "customer_response":
    case "customer_notified":
      return "Customer was notified";
    case "permanent_failure":
      return "Permanent failure";
    case "recovery_stopped":
      return "Recovery stopped";
    case "escalated":
      return "Escalated to operations";
    case "action_failed":
      return "Action could not complete";
    default:
      return value ? value.replace(/_/g, " ") : "Outcome recorded";
  }
}

export function actorLabel(eventType: string, actor: string): string {
  switch (eventType) {
    case "diagnosis":
      return "Diagnosis agent";
    case "strategy_proposed":
      return "Strategy engine";
    case "policy_decision":
      return "Policy guard";
    case "action_executed":
      return "Recovery action";
    case "recovery_signal":
      return "Outcome detector";
    case "adaptive_transition":
      return "Adaptive planner";
    case "intake_complete":
      return "Intake";
    case "case_created":
      return "Case opened";
    case "escalation":
      return "Escalation";
    default:
      return actor.replace(/_/g, " ");
  }
}

export interface RenderedEvent {
  actor: string;
  title: string;
  body: string;
  facts: { label: string; value: string }[];
  tone: "neutral" | "success" | "danger" | "warning";
  previousStrategy?: string;
  newStrategy?: string;
}

export function renderTimelineEvent(event: TimelineEvent): RenderedEvent {
  const data = event.metadata || {};
  const actor = actorLabel(event.event_type, event.actor);

  switch (event.event_type) {
    case "case_created":
      return {
        actor,
        title: "Recovery case opened",
        body: `${humanizeFailure(asString(data.failure_code), asString(data.failure_reason))} recorded for this payment.`,
        facts: [],
        tone: "neutral",
      };
    case "intake_complete":
      return {
        actor,
        title: asString(data.eligible) === "true" || data.eligible === true
          ? "Case accepted for recovery"
          : "Case not eligible for automated recovery",
        body: data.eligible === true
          ? "Payment context loaded. The case is eligible for automated recovery."
          : "This case is not currently eligible for automated recovery.",
        facts: [],
        tone: "neutral",
      };
    case "diagnosis":
      return {
        actor,
        title: humanizeCategory(asString(data.failure_category)),
        body: asString(data.root_cause) || "Failure classified from the payment context.",
        facts: [
          { label: "Confidence", value: formatConfidence(data.confidence) },
          ...asStringList(data.evidence).slice(0, 2).map((item) => ({
            label: "Evidence",
            value: humanizeEvidence(item),
          })),
        ],
        tone: data.is_recoverable === false ? "danger" : "neutral",
      };
    case "strategy_proposed": {
      const actionRaw = asString(data.action);
      const action = humanizeAction(actionRaw);
      const channel = humanizeChannel(asString(data.channel) || null);
      const delay = asNumber(data.retry_timing_hours);
      let title = action;
      if (actionRaw === "payment_reminder" && delay && delay > 0) {
        title = `${channel || "Customer"} reminder → retry in ${delay}h`;
      } else if (channel) {
        title = `${action} · ${channel}`;
      } else if (delay && delay > 0) {
        title = `${action} · ${delay}h`;
      }
      return {
        actor,
        title,
        body: asString(data.rationale) || "A recovery strategy was selected for this failure.",
        facts: delay && delay > 0 ? [{ label: "Scheduled", value: `in ${delay}h` }] : [],
        tone: "neutral",
      };
    }
    case "policy_decision":
      if (data.allowed === true) {
        return {
          actor,
          title: "Strategy approved",
          body: asString(data.reason) || "Within retry limits. No duplicate action detected.",
          facts: [],
          tone: "success",
        };
      }
      return {
        actor,
        title: data.mutated_action
          ? `Strategy modified · ${humanizeAction(asString(data.mutated_action))}`
          : "Strategy blocked",
        body: asString(data.reason) || "The policy guard prevented an unsafe recovery action.",
        facts: data.mutated_action
          ? [{ label: "Safe action", value: humanizeAction(asString(data.mutated_action)) }]
          : [],
        tone: "warning",
      };
    case "action_executed": {
      const result = asRecord(data.result);
      const actionRaw = asString(data.action);
      const action = humanizeAction(actionRaw);
      const simulated = asString(result.simulated_outcome);
      const response = asString(result.customer_response);
      let title = action;
      let body = `${action} simulated.`;
      if (simulated === "reminder_sent" || actionRaw === "payment_reminder") {
        title = "SMS reminder simulated";
        body = response
          ? "Customer notification sent and a response was recorded."
          : "Customer notification sent.";
      } else if (simulated === "customer_notified") {
        title = "Payment method update requested";
        body = "Customer was asked to update the payment method.";
      } else if (simulated === "recovery_successful") {
        title = "Payment retry";
        body = "Payment retry executed.";
      } else if (simulated === "recovery_failed") {
        title = "Payment retry";
        body = "Payment retry executed. The attempt did not recover the payment.";
      } else if (simulated === "escalated") {
        body = "Case handed to operations.";
      } else if (simulated === "recovery_stopped") {
        body = "Automated recovery was stopped.";
      }
      return {
        actor,
        title,
        body,
        facts: [],
        tone: simulated === "recovery_successful" ? "success" : "neutral",
      };
    }
    case "recovery_signal": {
      const context = asRecord(data.context);
      const signal = asString(data.signal_type);
      const simulated = asString(context.outcome);
      const response = asString(context.customer_response);
      const recovered = signal === "success" || simulated === "recovery_successful";
      let title = recovered ? "Payment recovered" : humanizeOutcome(signal, simulated);
      let body = humanizeOutcome(signal, simulated);
      if (signal === "no_response") {
        title = "Customer did not respond";
        body = "Customer did not respond to the payment reminder.";
      } else if (signal === "customer_response") {
        title = "Customer responded";
        body = response
          ? `Customer response recorded: ${response.replace(/_/g, " ")}.`
          : "The customer responded to the recovery action.";
      } else if (signal === "transient_failure") {
        title = "Recovery attempt unsuccessful";
        body = "Payment retry failed. Temporary failure persisted.";
      } else if (recovered) {
        title = "Payment recovered";
        body = "The simulated payment authorised successfully.";
      } else if (signal === "permanent_failure") {
        title = "Permanent failure";
        body = "Automated recovery is no longer appropriate.";
      }
      return {
        actor,
        title,
        body,
        facts: [],
        tone: recovered ? "success" : signal.includes("fail") || signal === "permanent_failure" ? "danger" : "neutral",
      };
    }
    case "adaptive_transition":
      return {
        actor,
        title: "Strategy changed",
        body: asString(data.transition_reason) || "The previous strategy did not produce a recovery signal. The planner changed the next action.",
        facts: [],
        tone: "warning",
        previousStrategy: humanizeAction(asString(data.previous_strategy_action)),
        newStrategy: humanizeAction(asString(data.new_strategy_action)),
      };
    case "escalation":
      return {
        actor,
        title: "Escalated",
        body: "Human intervention is required to continue recovery.",
        facts: [],
        tone: "danger",
      };
    case "recovery_complete":
      return {
        actor,
        title: "Recovery complete",
        body: "The case was successfully recovered.",
        facts: [],
        tone: "success",
      };
    case "recovery_stopped":
      return {
        actor,
        title: "Recovery stopped",
        body: asString(data.reason) || "Automated recovery is no longer appropriate.",
        facts: [],
        tone: "warning",
      };
    default:
      return {
        actor,
        title: event.event_type.replace(/_/g, " "),
        body: fallbackBody(event),
        facts: [],
        tone: "neutral",
      };
  }
}

function humanizeCategory(category: string): string {
  switch (category) {
    case "transient_technical":
      return "Transient technical failure";
    case "transient_customer":
      return "Transient customer failure";
    case "permanent_card":
      return "Permanent card failure";
    case "permanent_fraud":
      return "Permanent fraud indicator";
    case "ambiguous_decline":
      return "Ambiguous decline";
    case "recurring_failure":
      return "Recurring payment failure";
    default:
      return category ? category.replace(/_/g, " ") : "Failure diagnosed";
  }
}

function formatConfidence(value: unknown): string {
  const number = asNumber(value);
  if (number == null) return "—";
  const pct = number <= 1 ? number * 100 : number;
  return `${Math.round(pct)}%`;
}

function humanizeEvidence(value: string): string {
  return value
    .replace(/^Rule-based fallback:\s*/i, "")
    .replace(/_/g, " ");
}

function fallbackBody(event: TimelineEvent): string {
  const rationale = asString(event.metadata.rationale);
  const reason = asString(event.metadata.reason);
  const details = event.details;
  const candidate = rationale || reason || details;
  if (candidate && !candidate.trim().startsWith("{") && !candidate.trim().startsWith("[")) {
    return candidate;
  }
  return "Event recorded by the recovery workflow.";
}
