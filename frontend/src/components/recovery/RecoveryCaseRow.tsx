import type { QueueItem } from "../../types/recovery";
import { formatHours, formatINR } from "../../lib/format";
import { humanizeAction, humanizeFailure } from "../../lib/events";
import { displayStatus } from "../../lib/status";
import { CaseStatus } from "./CaseStatus";

interface Props {
  item: QueueItem;
  selected: boolean;
  onOpen: (caseId: string) => void;
  recoveredView?: boolean;
}

function latestActionCopy(item: QueueItem): string | null {
  if (!item.latest_action) return null;
  if (item.latest_action === "payment_reminder") return "SMS reminder sent";
  return humanizeAction(item.latest_action);
}

export function RecoveryCaseRow({ item, selected, onOpen, recoveredView }: Props) {
  const status = displayStatus(item);
  const failure = humanizeFailure(item.failure_type, item.failure_reason);
  const latest = latestActionCopy(item);

  return (
    <button
      type="button"
      className={`queue-row status-${status} ${selected ? "selected" : ""}`}
      onClick={() => onOpen(item.case_id)}
      aria-expanded={selected}
      aria-label={`Open recovery case ${item.payment_id}, ${formatINR(item.amount)}, ${status}`}
    >
      <span className="queue-id">{item.payment_id}</span>
      <span className="queue-amount">
        {recoveredView && item.recovered_amount != null
          ? `${formatINR(item.recovered_amount)} recovered`
          : formatINR(item.amount)}
      </span>
      <span className="queue-failure">{failure}</span>
      <span className="queue-status">
        <CaseStatus status={status} />
      </span>
      <div className="queue-meta">
        {recoveredView ? (
          <span>
            {item.attempt_count} {item.attempt_count === 1 ? "attempt" : "attempts"}
            {item.simulated_time_hours > 0
              ? ` · recovered after ${formatHours(item.simulated_time_hours)}`
              : ""}
          </span>
        ) : (
          <>
            {item.attempt_count > 0 && (
              <span>
                Attempt {item.attempt_count}
                {item.max_attempts ? ` of ${item.max_attempts}` : ""}
              </span>
            )}
            {latest && <span>{latest}</span>}
            {item.next_action && (
              <span>
                Next action · {humanizeAction(item.next_action)}
                {item.next_action_delay_hours ? ` in ${item.next_action_delay_hours}h` : ""}
              </span>
            )}
            {!item.next_action && item.workflow_started && item.can_advance && (
              <span>Next action · Continue recovery</span>
            )}
            {!item.workflow_started && <span>Waiting to run recovery</span>}
          </>
        )}
      </div>
    </button>
  );
}
