import { useEffect, useRef } from "react";
import type { QueueItem, TimelineEvent } from "../../types/recovery";
import { formatCustomer, formatHours, formatINR, formatPaymentType } from "../../lib/format";
import { humanizeAction, humanizeFailure } from "../../lib/events";
import { displayStatus, isNonRecoverableFailure, scenarioFromState } from "../../lib/status";
import { CaseStatus } from "./CaseStatus";
import { CaseTimeline } from "./CaseTimeline";
import { RecoveryControls } from "./RecoveryControls";

interface Props {
  item: QueueItem;
  events: TimelineEvent[];
  loadingTimeline: boolean;
  advancing: boolean;
  error: string | null;
  onClose: () => void;
  onAdvance: () => void;
}

export function CaseWorkspace({
  item,
  events,
  loadingTimeline,
  advancing,
  error,
  onClose,
  onAdvance,
}: Props) {
  const status = displayStatus(item);
  const scenario = scenarioFromState(item, events);
  const failure = humanizeFailure(item.failure_type, item.failure_reason);
  const nonRecoverable = isNonRecoverableFailure(item);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);

  // Derive NSF adaptive context for the header callout
  const isNSFInProgress =
    !nonRecoverable &&
    item.workflow_started &&
    (status === "recovering" || status === "awaiting_customer") &&
    item.attempt_count > 0;

  const latestSignalEvent = [...events]
    .reverse()
    .find((e) => e.event_type === "recovery_signal");
  const latestStrategyEvent = [...events]
    .reverse()
    .find((e) => e.event_type === "strategy_proposed" || e.event_type === "adaptive_transition");

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="case-workspace-title"
      >
        <header className="drawer-header">
          <div className="drawer-kicker">Recovery case</div>
          <div className="drawer-top">
            <div>
              <div className="drawer-id" id="case-workspace-title">
                {item.payment_id}
              </div>
              <div className="drawer-amount">{formatINR(item.amount)}</div>
              <div className="drawer-sub">{failure}</div>
            </div>
            <button
              ref={closeRef}
              type="button"
              className="icon-button"
              onClick={onClose}
              aria-label="Close case"
            >
              ×
            </button>
          </div>
          <div className="drawer-status-row">
            <CaseStatus status={status} />
            <span className="drawer-attempt">
              Attempt {item.attempt_count} of {item.max_attempts}
            </span>
          </div>

          {/* Non-recoverable permanent failure — shown in header before workflow runs */}
          {nonRecoverable && !item.workflow_started && (
            <div className="non-recoverable-header-callout">
              <span className="callout-icon" aria-hidden="true">⚠</span>
              <div>
                <strong>Non-recoverable payment method</strong>
                <p>
                  {failure} cannot be recovered by automated retry. No recovery action will be attempted.
                  Customer must update their payment method or escalate to operations.
                </p>
              </div>
            </div>
          )}

          {/* Next action callout — only for recoverable cases that can advance */}
          {item.next_action && item.can_advance && !nonRecoverable && (
            <div className="next-action-callout">
              <span>Next action</span>
              <strong>
                {humanizeAction(item.next_action)}
                {item.next_action_delay_hours ? ` in ${item.next_action_delay_hours}h` : ""}
              </strong>
            </div>
          )}

          {/* NSF adaptive loop context: shows current attempt, customer response, next strategy */}
          {isNSFInProgress && (
            <div className="nsf-adaptive-context">
              <div className="nsf-context-row">
                <span className="nsf-context-label">Attempt</span>
                <strong>{item.attempt_count} of {item.max_attempts}</strong>
              </div>
              {latestSignalEvent && (
                <div className="nsf-context-row">
                  <span className="nsf-context-label">Customer response</span>
                  <strong>
                    {latestSignalEvent.metadata.signal_type === "no_response"
                      ? "No response to reminder"
                      : latestSignalEvent.metadata.signal_type === "customer_response"
                      ? "Responded"
                      : String(latestSignalEvent.metadata.signal_type || "—").replace(/_/g, " ")}
                  </strong>
                </div>
              )}
              {latestStrategyEvent && (
                <div className="nsf-context-row">
                  <span className="nsf-context-label">Next strategy</span>
                  <strong>
                    {humanizeAction(
                      String(
                        latestStrategyEvent.metadata.new_strategy_action ||
                        latestStrategyEvent.metadata.action || ""
                      )
                    )}
                    {latestStrategyEvent.metadata.retry_timing_hours
                      ? ` in ${String(latestStrategyEvent.metadata.retry_timing_hours)}h`
                      : ""}
                  </strong>
                </div>
              )}
            </div>
          )}

          {scenario && (
            <div className="scenario-note">
              <strong>{scenario.label}</strong>
              {scenario.description}
            </div>
          )}
        </header>

        <div className="summary-grid">
          <div className="summary-item">
            <span>Payment</span>
            <strong>{formatINR(item.amount)}</strong>
          </div>
          <div className="summary-item">
            <span>Failure</span>
            <strong>{failure}</strong>
          </div>
          <div className="summary-item">
            <span>Customer</span>
            <strong>{formatCustomer(item.customer_id)}</strong>
          </div>
          <div className="summary-item">
            <span>Payment type</span>
            <strong>{formatPaymentType(item.payment_method)}</strong>
          </div>
          <div className="summary-item">
            <span>Attempts</span>
            <strong>
              {item.attempt_count} / {item.max_attempts}
            </strong>
          </div>
          <div className="summary-item">
            <span>Recovery duration</span>
            <strong>
              {item.simulated_time_hours > 0 ? formatHours(item.simulated_time_hours) : "Not started"}
            </strong>
          </div>
        </div>

        <div className="drawer-body">
          <CaseTimeline events={events} loading={loadingTimeline} item={item} />
        </div>

        <RecoveryControls
          item={item}
          status={status}
          advancing={advancing}
          error={error}
          onAdvance={onAdvance}
        />
      </aside>
    </>
  );
}
