import type { Metrics } from "../../types/recovery";
import { formatINR, formatPercent } from "../../lib/format";

interface Props {
  metrics: Metrics | null;
  loading: boolean;
}

export function MetricsStrip({ metrics, loading }: Props) {
  if (loading && !metrics) {
    return (
      <section className="metrics-strip" aria-busy="true">
        {[0, 1, 2].map((key) => (
          <article className="metric-card" key={key}>
            <div className="skeleton" style={{ width: "40%" }} />
            <div className="skeleton lg" style={{ marginTop: 12 }} />
          </article>
        ))}
      </section>
    );
  }

  return (
    <section className="metrics-strip" aria-label="Recovery metrics">
      <article className="metric-card risk">
        <div className="metric-label">Revenue at risk</div>
        <div className="metric-value">{formatINR(metrics?.revenue_at_risk ?? 0)}</div>
        <div className="metric-hint">Active unresolved payment value</div>
      </article>
      <article className="metric-card success">
        <div className="metric-label">Revenue recovered</div>
        <div className="metric-value">{formatINR(metrics?.revenue_recovered ?? 0)}</div>
        <div className="metric-hint">Successfully recovered</div>
      </article>
      <article className="metric-card">
        <div className="metric-label">Recovery rate</div>
        <div className="metric-value">{formatPercent(metrics?.recovery_rate_percent ?? 0)}</div>
        <div className="metric-hint">Recovered revenue / eligible recovery value</div>
      </article>
    </section>
  );
}
