interface Props {
  lastUpdated: string | null;
  onReset: () => void;
  resetting: boolean;
  darkMode: boolean;
  onToggleTheme: () => void;
  currentView?: "operations" | "results";
  onViewChange?: (view: "operations" | "results") => void;
  statusText?: string | null;
}

export function Header({ lastUpdated, onReset, resetting, darkMode, onToggleTheme, currentView, onViewChange, statusText }: Props) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-kicker">AI Revenue Recovery</div>
        {currentView && onViewChange ? (
          <nav className="view-switcher" aria-label="Main Navigation">
            <button 
              className={`view-btn ${currentView === 'operations' ? 'active' : ''}`}
              onClick={() => onViewChange('operations')}
            >
              Recovery Operations
            </button>
            <button 
              className={`view-btn ${currentView === 'results' ? 'active' : ''}`}
              onClick={() => onViewChange('results')}
            >
              Results
            </button>
          </nav>
        ) : (
          <div className="brand-title">Recovery Operations</div>
        )}
      </div>
      <div className="header-meta">
        <div className="env-pill">
          <span className="env-dot" aria-hidden="true" />
          Local simulation
        </div>
        <div className="header-updated">
          {statusText ? statusText : lastUpdated ? `Last updated: ${lastUpdated}` : "Waiting for data"}
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
