import type { DisplayStatus } from "../../types/recovery";
import { statusLabel } from "../../lib/status";

export function CaseStatus({ status }: { status: DisplayStatus }) {
  return <span className={`status-label ${status}`}>{statusLabel(status)}</span>;
}
