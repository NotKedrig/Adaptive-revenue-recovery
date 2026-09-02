import type { DisplayStatus, QueueItem } from "../../types/recovery";
import { isNonRecoverableFailure, isTerminalStatus } from "../../lib/status";

interface Props {
  item: QueueItem;
  status: DisplayStatus;
  advancing: boolean;
  error: string | null;
  onAdvance: () => void;
}

export function RecoveryControls({ item, status, advancing, error, onAdvance }: Props) {
  const terminal = isTerminalStatus(item);
  const nonRecoverable = isNonRecoverableFailure(item);

  // Permanent failures that haven't been through the workflow yet:
  // The first "advance" would immediately escalate — show the outcome upfront
  // instead of a misleading "Run recovery" button.
  const preRunPermanent = nonRecoverable && !item.workflow_started;

  let controlLabel = "Run recovery";
  if (item.workflow_started) controlLabel = "Advance recovery";
  if (advancing) controlLabel = "Working…";

  return (
    <footer className="drawer-footer">
      {error && (
        <p className="banner error" style={{ margin: "0 0 12px" }}>
          {error}
        </p>
      )}
      {terminal ? (
        <p className={`terminal-note ${status === "recovered" ? "success" : "danger"}`}>
          {status === "recovered" && "Recovered. Automated recovery is complete."}
          {status === "escalated" &&
            "Escalated — non-recoverable. This payment method cannot be retried. Manual resolution or customer card update required."}
          {status === "stopped" && "Recovery stopped. Automated actions are disabled."}
        </p>
      ) : preRunPermanent ? (
        <div className="non-recoverable-notice">
          <span className="non-recoverable-icon" aria-hidden="true">⚠</span>
          <div>
            <strong>Non-recoverable failure</strong>
            <p>
              {item.failure_reason || item.failure_type} cannot be retried automatically.
              No recovery action will be taken. Escalate to operations or notify the customer
              to update their payment method.
            </p>
          </div>
        </div>
      ) : (
        <button
          id="advance-recovery-btn"
          type="button"
          className="btn-primary"
          onClick={onAdvance}
          disabled={advancing || !item.can_advance}
        >
          {controlLabel}
        </button>
      )}
    </footer>
  );
}
