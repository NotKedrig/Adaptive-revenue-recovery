import { looksLikeRawObject } from "../../lib/format";
import { renderTimelineEvent } from "../../lib/events";
import type { TimelineEvent as TimelineEventData } from "../../types/recovery";

export function TimelineEvent({ event }: { event: TimelineEventData }) {
  const rendered = renderTimelineEvent(event);
  const body = looksLikeRawObject(rendered.body)
    ? "Event recorded by the recovery workflow."
    : rendered.body;

  return (
    <li className={`timeline-item ${rendered.tone}`}>
      <span className="timeline-dot" aria-hidden="true" />
      <div className="event-actor">{rendered.actor}</div>
      <div className="event-title">{rendered.title}</div>
      {body && <p className="event-body">{body}</p>}
      {rendered.facts.length > 0 && (
        <div className="event-facts">
          {rendered.facts.map((fact) => (
            <span key={`${fact.label}-${fact.value}`}>
              <em>{fact.label}</em>
              {fact.value}
            </span>
          ))}
        </div>
      )}
      {rendered.previousStrategy && rendered.newStrategy && (
        <div className="adapt-block" aria-label="Strategy transition">
          <div className="adapt-card">
            <span>Previous strategy</span>
            <strong>{rendered.previousStrategy}</strong>
          </div>
          <div className="adapt-arrow">↓</div>
          <div className="adapt-card">
            <span>Outcome observed</span>
            <strong>Previous attempt did not recover the payment</strong>
          </div>
          <div className="adapt-arrow">↓ Adaptive planner · strategy changed</div>
          <div className="adapt-card new">
            <span>New strategy</span>
            <strong>{rendered.newStrategy}</strong>
          </div>
        </div>
      )}
    </li>
  );
}
