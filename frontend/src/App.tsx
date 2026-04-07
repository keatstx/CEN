import { useEffect, useState } from "react";
import type { ReadyResponse } from "./types";
import { fetchReady } from "./api";
import Layout from "./components/Layout";
import Executor from "./components/Executor";
import DAGViewer from "./components/DAGViewer";

type Tab = "executor" | "dag-viewer";

export default function App() {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("executor");
  const [dagSelectedModule, setDagSelectedModule] = useState("");

  useEffect(() => {
    fetchReady()
      .then(setReady)
      .catch((err) => setError(err.message));
  }, []);

  const tabs: { key: Tab; label: string }[] = [
    { key: "executor", label: "Executor" },
    { key: "dag-viewer", label: "DAG Viewer" },
  ];

  return (
    <Layout ready={ready} error={error}>
      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-[var(--color-border)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
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

      {activeTab === "executor" && (
        <Executor modules={ready?.modules_loaded ?? []} />
      )}

      {activeTab === "dag-viewer" && (
        <DAGViewer
          modules={ready?.modules_loaded ?? []}
          selectedModule={dagSelectedModule}
          onModuleChange={setDagSelectedModule}
        />
      )}
    </Layout>
  );
}
