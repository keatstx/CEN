import { useEffect, useState } from "react";
import type { ReadyResponse, WorkflowResult } from "./types";
import { fetchReady, executeWorkflow } from "./api";
import Layout from "./components/Layout";
import ModuleSelector from "./components/ModuleSelector";
import WorkflowForm from "./components/WorkflowForm";
import ResultPanel from "./components/ResultPanel";

export default function App() {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);

  useEffect(() => {
    fetchReady()
      .then(setReady)
      .catch((err) => setError(err.message));
  }, []);

  const handleModuleChange = (mod: string) => {
    setSelectedModule(mod);
    setResult(null);
  };

  const handleExecute = async (context: Record<string, unknown>) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await executeWorkflow({
        module_name: selectedModule,
        context,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout ready={ready} error={error}>
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
                onExecute={handleExecute}
              />
            </div>
          )}
        </div>

        {/* Right column — results */}
        <div className="lg:col-span-3">
          {result ? (
            <div className="card">
              <ResultPanel result={result} />
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
    </Layout>
  );
}
