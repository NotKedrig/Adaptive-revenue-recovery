interface Props {
  lastUpdated: string | null;
  onReset: () => void;
  resetting: boolean;
}

export function Header({ lastUpdated, onReset, resetting }: Props) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-kicker">AI Revenue Recovery</div>
        <div className="brand-title">Recovery Operations</div>
      </div>
      <div className="header-meta">
        <div className="env-pill">
          <span className="env-dot" aria-hidden="true" />
          Local simulation
        </div>
        <div className="header-updated">
          {lastUpdated ? `Last updated: ${lastUpdated}` : "Waiting for data"}
        </div>
        <button type="button" className="header-reset" onClick={onReset} disabled={resetting}>
          {resetting ? "Loading demo…" : "Reset demo"}
        </button>
      </div>
    </header>
  );
}
