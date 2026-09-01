import type { QueueItem, TimelineEvent as TimelineEventData } from "../../types/recovery";
import { formatINR } from "../../lib/format";
import { displayStatus } from "../../lib/status";
import { LoadingState } from "../feedback/LoadingState";
import { EmptyState } from "../feedback/EmptyState";
import { TimelineEvent } from "./TimelineEvent";

export function CaseTimeline({
  events,
  loading,
  item,
}: {
  events: TimelineEventData[];
  loading: boolean;
  item: QueueItem;
}) {
  if (loading) {
    return (
      <div style={{ padding: "16px 22px" }}>
        <LoadingState lines={3} />
      </div>
    );
  }

  if (events.length === 0) {
    return <EmptyState>No recovery events yet. Run recovery to start the workflow.</EmptyState>;
  }

  const status = displayStatus(item);

  return (
    <>
      <ol className="timeline">
        {events.map((event) => (
          <TimelineEvent key={event.id} event={event} />
        ))}
      </ol>
      {status === "recovered" && (
        <div className="complete-banner">
          Recovery complete
          {item.recovered_amount != null
            ? `. ${formatINR(item.recovered_amount)} recovered after ${item.attempt_count} ${
                item.attempt_count === 1 ? "attempt" : "attempts"
              }.`
            : ". The case was successfully recovered."}
        </div>
      )}
    </>
  );
}
