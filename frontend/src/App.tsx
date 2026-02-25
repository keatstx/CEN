import { useEffect, useState } from "react";
import type { ReadyResponse, Session, WorkflowResult } from "./types";
import { fetchReady, createSession, getSession, executeWorkflow, approveSession } from "./api";
import Layout from "./components/Layout";
import ModuleSelector from "./components/ModuleSelector";
import WorkflowForm from "./components/WorkflowForm";
import ResultPanel from "./components/ResultPanel";
import DAGViewer from "./components/DAGViewer";

type Tab = "executor" | "dag-viewer";

export default function App() {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState("");
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("executor");

  useEffect(() => {
    fetchReady()
      .then(setReady)
      .catch((err) => setError(err.message));
  }, []);

  const handleModuleChange = (mod: string) => {
    setSelectedModule(mod);
    setSession(null);
    setResult(null);
  };

  const handleNewSession = () => {
    setSession(null);
    setResult(null);
  };

  const handleExecute = async (context: Record<string, unknown>) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const sess = await createSession(selectedModule, context);
      const res = await executeWorkflow(
        { module_name: selectedModule, context },
        sess.id,
      );
      setResult(res);
      const updatedSession = await getSession(sess.id);
      setSession(updatedSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const res = await approveSession(session.id);
      setResult(res);
      const updatedSession = await getSession(session.id);
      setSession(updatedSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setLoading(false);
    }
  };

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
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Left column — controls */}
          <div className="lg:col-span-2 space-y-6">
            <div className="card">
              <ModuleSelector
                modules={ready?.modules_loaded ?? []}
                selected={selectedModule}
                onSelect={handleModuleChange}
              />
            </div>
            {selectedModule && (
              <div className="card">
                <WorkflowForm
                  moduleName={selectedModule}
                  loading={loading}
                  sessionStatus={session?.status ?? null}
                  onExecute={handleExecute}
                  onNewSession={handleNewSession}
                />
              </div>
            )}
          </div>

          {/* Right column — results */}
          <div className="lg:col-span-3">
            {result ? (
              <div className="card">
                <ResultPanel
                  result={result}
                  session={session}
                  loading={loading}
                  onApprove={handleApprove}
                />
              </div>
            ) : (
              <div className="card flex items-center justify-center min-h-[300px]">
                <p className="text-subtle text-center">
                  {selectedModule
                    ? "Fill in the context and execute the workflow to see results."
                    : "Select a module to get started."}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "dag-viewer" && (
        <DAGViewer
          modules={ready?.modules_loaded ?? []}
          selectedModule={selectedModule}
          onModuleChange={handleModuleChange}
        />
      )}
    </Layout>
  );
}
