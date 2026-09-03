import { useEffect, useState, useCallback } from "react";
import { Header } from "../components/layout/Header";
import { getBaselineComparison } from "../services/api";
import type { BaselineComparison } from "../types/recovery";
import { formatINR } from "../lib/format";

interface Props {
  darkMode: boolean;
  onToggleTheme: () => void;
  onViewChange: (view: "operations" | "results") => void;
}

export function ResultsPage({ darkMode, onToggleTheme, onViewChange }: Props) {
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

  let statusText = "Benchmark ready";
  if (failed) statusText = "Benchmark unavailable";
  else if (loading && !data) statusText = "Fetching evaluation…";

  return (
    <div className="app-shell">
      <Header
        lastUpdated={null}
        statusText={statusText}
        onReset={() => {}}
        resetting={false}
        darkMode={darkMode}
        onToggleTheme={onToggleTheme}
        currentView="results"
        onViewChange={onViewChange}
      />
      <main className="page">
        {failed && (
          <div className="banner error" role="alert">
            Failed to load benchmark results. Please check if the backend is running.
          </div>
        )}
        {loading && !data && (
          <div className="loading-state">
            <div className="skeleton lg" style={{ marginBottom: 24 }} />
            <div className="skeleton" style={{ marginBottom: 12 }} />
            <div className="skeleton" />
          </div>
        )}
        {data && (
          <section className="results-container">
            <header className="results-header">
              <h1 className="results-title">RECOVERY RESULTS</h1>
              <p className="results-subtitle">Deterministic evaluation · {data.case_count} cases</p>
              <p className="results-desc">
                Adaptive recovery recovered more at-risk revenue than a naive single-retry strategy.
              </p>
            </header>

            <div className="results-table-card">
              <table className="results-table">
                <thead>
                  <tr>
                    <th></th>
                    <th className="align-right">NAIVE RETRY</th>
                    <th className="align-right">ADAPTIVE RECOVERY</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Cases</td>
                    <td className="align-right">{data.case_count}</td>
                    <td className="align-right">{data.case_count}</td>
                  </tr>
                  <tr>
                    <td>Revenue at risk</td>
                    <td className="align-right">{formatINR(data.total_revenue_at_risk, true)}</td>
                    <td className="align-right">{formatINR(data.total_revenue_at_risk, true)}</td>
                  </tr>
                  <tr>
                    <td>Revenue recovered</td>
                    <td className="align-right">{formatINR(data.naive.recovered_revenue, true)}</td>
                    <td className="align-right">{formatINR(data.adaptive.recovered_revenue, true)}</td>
                  </tr>
                  <tr>
                    <td>Recovery rate</td>
                    <td className="align-right">{data.naive.recovery_rate_percent.toFixed(2)}%</td>
                    <td className="align-right">{data.adaptive.recovery_rate_percent.toFixed(2)}%</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="results-highlight-card">
              <div className="highlight-improvement">
                +{data.improvement_percentage_points.toFixed(1)} percentage points
              </div>
              <div className="highlight-revenue">
                {formatINR(Math.abs(data.additional_revenue_recovered), true)} additional revenue recovered
              </div>
            </div>

            <div className="results-methodology">
              <h2>METHODOLOGY</h2>
              <p>
                Same {data.case_count} deterministic cases and same underlying outcome simulation model for both strategies.
              </p>
              <div className="methodology-grid">
                <div>
                  <h3>Naive:</h3>
                  <p>One immediate retry, no diagnosis, no adaptation.</p>
                </div>
                <div>
                  <h3>Adaptive:</h3>
                  <p>Diagnosis → bounded strategy → policy guard → recovery action → outcome detection → adaptive follow-up.</p>
                </div>
              </div>
            </div>

            <div className="results-disclaimer banner">
              <strong>IMPORTANT:</strong> Product-level deterministic simulation; not a statistically significant experiment.
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
