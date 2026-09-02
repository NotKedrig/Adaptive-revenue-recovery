interface Props {
  lastUpdated: string | null;
  onReset: () => void;
  resetting: boolean;
  darkMode: boolean;
  onToggleTheme: () => void;
}

export function Header({ lastUpdated, onReset, resetting, darkMode, onToggleTheme }: Props) {
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
        <button
          id="theme-toggle-btn"
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
          title={darkMode ? "Light mode" : "Dark mode"}
        >
          {darkMode ? "☀" : "🌙"}
        </button>
        <button type="button" className="header-reset" onClick={onReset} disabled={resetting}>
          {resetting ? "Loading demo…" : "Reset demo"}
        </button>
      </div>
    </header>
  );
}
