import { useEffect, useState } from "react";
import type { BaselineComparison } from "../../types/recovery";
import { getBaselineComparison } from "../../services/api";
import { formatINR } from "../../lib/format";

/**
 * A small, single-line callout below the metrics strip showing the
 * adaptive vs naive baseline comparison. Fetches once on mount,
 * fails gracefully without breaking the queue.
 */
export function BaselineCallout() {
  const [data, setData] = useState<BaselineComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getBaselineComparison()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Fail silently — never break the main queue
  if (failed || (!loading && !data)) return null;

  if (loading) {
    return (
      <div className="baseline-callout baseline-callout--loading" aria-busy="true">
        <span className="baseline-dot" aria-hidden="true" />
        <span>Loading benchmark…</span>
      </div>
    );
  }

  if (!data) return null;

  const sign = data.improvement_percentage_points >= 0 ? "+" : "";
  const ppLabel = `${sign}${data.improvement_percentage_points.toFixed(1)} pp vs. naive retry`;
  const revenueLabel = formatINR(Math.abs(data.additional_revenue_recovered), true);

  return (
    <div
      className="baseline-callout"
      title={`Deterministic ${data.case_count}-case evaluation (seed ${data.evaluation_seed}). Local simulation only — no external API calls.`}
      aria-label={`Adaptive recovery benchmark: ${ppLabel}`}
    >
      <div className="baseline-kicker">
        BENCHMARK <span className="baseline-sep">·</span> {data.case_count}-CASE SIMULATION
      </div>
      <div className="baseline-main">
        Adaptive recovery <strong className="baseline-improvement">{ppLabel}</strong>
      </div>
      <div className="baseline-sub">
        {revenueLabel} additional revenue recovered
      </div>
    </div>
  );
}
