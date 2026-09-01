import React, { useEffect, useState } from 'react';

export interface TimelineEvent {
  event_type: string;
  timestamp: string;
  actor: string;
  status: string;
  summary: string;
  details: string;
  metadata: any;
}

export interface CaseTimelineProps {
  caseId: string;
  onClose: () => void;
}

export const CaseTimeline: React.FC<CaseTimelineProps> = ({ caseId, onClose }) => {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/cases/${caseId}/timeline`)
      .then(res => res.json())
      .then(data => {
        setEvents(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [caseId]);

  return (
    <div className="timeline-overlay">
      <div className="timeline-modal">
        <div className="timeline-header">
          <h2>Case Timeline: {caseId}</h2>
          <button className="timeline-close" onClick={onClose}>×</button>
        </div>
        <div className="timeline-content">
          {loading ? (
            <p className="timeline-loading">Loading events...</p>
          ) : events.length === 0 ? (
            <p className="timeline-empty">No events recorded for this case yet.</p>
          ) : (
            <ul className="timeline-list">
              {events.map((ev, i) => {
                const date = new Date(ev.timestamp);
                const timeString = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                
                return (
                  <li key={i} className={`timeline-event event-status-${ev.status}`}>
                    <div className="event-meta">
                      <span className="event-time">{timeString}</span>
                      <span className="event-actor">{ev.actor}</span>
                    </div>
                    <div className="event-body">
                      <h4 className="event-summary">{ev.summary}</h4>
                      {ev.details && <p className="event-details">{ev.details}</p>}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
