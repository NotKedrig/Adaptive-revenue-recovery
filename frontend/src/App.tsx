import { useState, useCallback } from "react";
import { RecoveryQueuePage } from "./pages/RecoveryQueuePage";
import { ResultsPage } from "./pages/ResultsPage";
import "./index.css";
import "./results.css";

export type TopLevelView = "operations" | "results";

export default function App() {
  const [view, setView] = useState<TopLevelView>("operations");
  const [darkMode, setDarkMode] = useState(() => {
    return document.documentElement.getAttribute("data-theme") === "dark";
  });

  const toggleTheme = useCallback(() => {
    setDarkMode((prev) => {
      const next = !prev;
      document.documentElement.setAttribute("data-theme", next ? "dark" : "light");
      return next;
    });
  }, []);

  return (
    <>
      {view === "operations" && (
        <RecoveryQueuePage 
          currentView={view} 
          onViewChange={setView} 
          darkMode={darkMode}
          onToggleTheme={toggleTheme}
        />
      )}
      {view === "results" && (
        <ResultsPage 
          currentView={view} 
          onViewChange={setView} 
          darkMode={darkMode}
          onToggleTheme={toggleTheme}
        />
      )}
    </>
  );
}
