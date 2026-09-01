import { useEffect, useState } from "react";
import { Header } from "../components/layout/Header";
import { MetricsStrip } from "../components/metrics/MetricsStrip";
import { RecoveryCaseRow } from "../components/recovery/RecoveryCaseRow";
import { CaseWorkspace } from "../components/recovery/CaseWorkspace";
import { Toast } from "../components/feedback/Toast";
import { ConfirmDialog } from "../components/feedback/ConfirmDialog";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingState } from "../components/feedback/LoadingState";
import { useRecoveryConsole } from "../hooks/useRecoveryConsole";

export function RecoveryQueuePage() {
  const consoleState = useRecoveryConsole();
  const [tab, setTab] = useState<"active" | "recovered">("active");
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") consoleState.closeCase();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [consoleState.closeCase]);

  const rows = tab === "active" ? consoleState.queue : consoleState.recovered;

  return (
    <div className="app-shell">
      <Header
        lastUpdated={consoleState.lastUpdated}
        resetting={consoleState.demoLoading}
        onReset={() => setConfirmReset(true)}
      />

      <main className={`page ${consoleState.selected ? "subdued" : ""}`}>
        {consoleState.unavailable && (
          <div className="banner error" role="alert">
            Recovery service unavailable. Check that the local backend is running.
          </div>
        )}

        {consoleState.demoLoading && (
          <div className="banner">Loading deterministic recovery scenarios...</div>
        )}

        <MetricsStrip metrics={consoleState.metrics} loading={consoleState.loading} />

        <section className="queue-panel">
          <div className="queue-toolbar">
            <h1 className="queue-title">Recovery queue</h1>
          </div>
          <div className="tabs" role="tablist" aria-label="Queue views">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "active"}
              className={`tab ${tab === "active" ? "active" : ""}`}
              onClick={() => setTab("active")}
            >
              Live Queue ({consoleState.queue.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "recovered"}
              className={`tab ${tab === "recovered" ? "active" : ""}`}
              onClick={() => setTab("recovered")}
            >
              Recovered ({consoleState.recovered.length})
            </button>
          </div>

          {consoleState.loading && rows.length === 0 ? (
            <div style={{ padding: 20 }}>
              <LoadingState lines={3} />
            </div>
          ) : rows.length === 0 ? (
            <EmptyState>
              {tab === "active" ? "No active recovery cases." : "No recovered cases yet."}
            </EmptyState>
          ) : (
            rows.map((item) => (
              <RecoveryCaseRow
                key={item.case_id}
                item={item}
                selected={item.case_id === consoleState.selectedId}
                recoveredView={tab === "recovered"}
                onOpen={consoleState.openCase}
              />
            ))
          )}
        </section>
      </main>

      {consoleState.selected && (
        <CaseWorkspace
          item={consoleState.selected}
          events={consoleState.events}
          loadingTimeline={consoleState.timelineLoading}
          advancing={consoleState.advancing}
          error={consoleState.actionError}
          onClose={consoleState.closeCase}
          onAdvance={consoleState.advance}
        />
      )}

      {consoleState.toast && (
        <Toast
          title={consoleState.toast.title}
          body={consoleState.toast.body}
          onDismiss={consoleState.dismissToast}
        />
      )}

      {confirmReset && (
        <ConfirmDialog
          title="Reset demo data?"
          body="This replaces the current queue with the three deterministic recovery scenarios."
          confirmLabel="Reset demo"
          onCancel={() => setConfirmReset(false)}
          onConfirm={() => {
            setConfirmReset(false);
            void consoleState.resetDemo();
          }}
        />
      )}
    </div>
  );
}
