import { useEffect, useState } from "react";
import type { ReadyResponse, Session } from "./types";
import { fetchReady } from "./api";
import Layout from "./components/Layout";
import Dashboard from "./components/Dashboard";
import Executor from "./components/Executor";
import DAGViewer from "./components/DAGViewer";
import SOPStudio from "./components/SOPStudio";
import Concierge from "./components/Concierge";

type Tab = "dashboard" | "executor" | "dag-viewer" | "sop-studio";

export default function App() {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [dagSelectedModule, setDagSelectedModule] = useState("");
  // The case the navigator is currently focused on. Held at App
  // level so the persistent Concierge in the right rail can read it
  // regardless of which tab is active. Executor pushes its
  // internal activeCase up via the onActiveCaseChange callback.
  const [activeCase, setActiveCase] = useState<Session | null>(null);
  // When the user clicks a card on the Dashboard, App passes this id
  // to Executor and switches tabs. Executor hydrates the case and
  // pushes the result back up via onActiveCaseChange.
  const [executorPreselect, setExecutorPreselect] = useState<string | null>(null);
  // Bumped each time the user (re-)opens the Dashboard tab so the
  // queue refetches with the latest state.
  const [dashboardRefreshKey, setDashboardRefreshKey] = useState(0);

  const refreshReady = () => {
    fetchReady()
      .then(setReady)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    refreshReady();
  }, []);

  const tabs: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" },
    { key: "executor", label: "Executor" },
    { key: "dag-viewer", label: "DAG Viewer" },
    { key: "sop-studio", label: "SOP Studio" },
  ];

  const handleTabClick = (key: Tab) => {
    setActiveTab(key);
    if (key === "dashboard") {
      setDashboardRefreshKey((k) => k + 1);
    }
  };

  const handleCaseSelectedFromDashboard = (caseId: string) => {
    setExecutorPreselect(caseId);
    setActiveTab("executor");
  };

  // The persistent right-rail concierge — same instance across every
  // tab. Reads activeCase from App-level state so it follows the
  // navigator wherever they go.
  const rightRail = (
    <Concierge caseRecord={activeCase} />
  );

  return (
    <Layout ready={ready} error={error} rightRail={rightRail}>
      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-[var(--color-border)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => handleTabClick(t.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors relative -mb-px ${
              activeTab === t.key
                ? "text-[var(--color-accent)] border-b-2 border-[var(--color-accent)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "dashboard" && (
        <Dashboard
          onCaseSelected={handleCaseSelectedFromDashboard}
          refreshKey={dashboardRefreshKey}
        />
      )}

      {activeTab === "executor" && (
        <Executor
          modules={ready?.modules_loaded ?? []}
          initialCaseId={executorPreselect}
          onActiveCaseChange={setActiveCase}
        />
      )}

      {activeTab === "dag-viewer" && (
        <DAGViewer
          modules={ready?.modules_loaded ?? []}
          selectedModule={dagSelectedModule}
          onModuleChange={setDagSelectedModule}
        />
      )}

      {activeTab === "sop-studio" && (
        <SOPStudio onModulePromoted={refreshReady} />
      )}
    </Layout>
  );
}
