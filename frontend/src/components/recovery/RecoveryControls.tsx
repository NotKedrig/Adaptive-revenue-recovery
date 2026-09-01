import type { DisplayStatus, QueueItem } from "../../types/recovery";
import { isTerminalStatus } from "../../lib/status";

interface Props {
  item: QueueItem;
  status: DisplayStatus;
  advancing: boolean;
  error: string | null;
  onAdvance: () => void;
}

export function RecoveryControls({ item, status, advancing, error, onAdvance }: Props) {
  const terminal = isTerminalStatus(item);
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
          {status === "escalated" && "Escalated. Human intervention required."}
          {status === "stopped" && "Recovery stopped. Automated actions are disabled."}
        </p>
      ) : (
        <button
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
