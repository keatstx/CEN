import { useCallback, useEffect, useMemo, useState } from "react";
import {
  approveSession,
  createCase,
  createProject,
  deleteCase,
  executeWorkflow,
  getCase,
  listCases,
  listProjects,
  provideInput,
  rewindCase,
} from "../api";
import type { Project, Session } from "../types";
import CaseSidebar from "./CaseSidebar";
import Concierge from "./Concierge";
import Documents from "./Documents";
import InformationSoFar from "./InformationSoFar";
import StepCard from "./StepCard";
import Stepper from "./Stepper";

interface Props {
  modules: string[];
}

/**
 * Three-frame Executor: project/case nav (left), interactive step
 * card (middle), AI Concierge placeholder (right).
 *
 * Drives the new step-pause flow end-to-end:
 *   1. Pick or create a project.
 *   2. Pick a module + create a new case.
 *   3. Engine runs until it hits AWAITING_INPUT or AWAITING_APPROVAL.
 *   4. Middle frame renders the form/approval card.
 *   5. User submits → /provide_input or /approve → engine resumes
 *      from cached node outputs (no duplicate side effects).
 *   6. Repeat until COMPLETED.
 */
export default function Executor({ modules }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState("");
  const [cases, setCases] = useState<Session[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeCase, setActiveCase] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Returns true if the error looks like a case 404 (stale id). */
  const isStaleCaseError = (e: unknown): boolean => {
    if (e instanceof Error) {
      const status = (e as Error & { status?: number }).status;
      if (status === 404) return true;
    }
    const msg = e instanceof Error ? e.message : String(e);
    return /not found/i.test(msg);
  };

  /** Returns true if the error is a 409 (wrong state — case advanced). */
  const isWrongStateError = (e: unknown): boolean => {
    if (e instanceof Error) {
      const status = (e as Error & { status?: number }).status;
      if (status === 409) return true;
    }
    return false;
  };

  /** Clear the stale case from local state and refresh the list. */
  const clearStaleCase = async () => {
    setSelectedCaseId(null);
    setActiveCase(null);
    await refreshCases();
  };

  /** Re-fetch the active case so the UI catches up to the backend's state. */
  const resyncCase = async (id: string) => {
    try {
      const fresh = await getCase(id);
      setActiveCase(fresh);
      await refreshCases();
    } catch {
      // If the resync itself 404s, clear instead.
      await clearStaleCase();
    }
  };

  // Load projects on mount.
  useEffect(() => {
    listProjects()
      .then((p) => {
        setProjects(p);
        if (p.length > 0 && selectedProjectId === null) {
          setSelectedProjectId(p[0].id);
        }
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load cases for the selected project.
  const refreshCases = useCallback(async () => {
    if (!selectedProjectId) {
      setCases([]);
      return;
    }
    try {
      const list = await listCases({
        project_id: selectedProjectId,
        limit: 100,
      });
      setCases(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    }
  }, [selectedProjectId]);

  useEffect(() => {
    refreshCases();
  }, [refreshCases]);

  // Load active case when selectedCaseId changes.
  useEffect(() => {
    if (!selectedCaseId) {
      setActiveCase(null);
      return;
    }
    getCase(selectedCaseId)
      .then(setActiveCase)
      .catch((e) => {
        if (isStaleCaseError(e)) {
          // Stale id from a redeploy or external delete — clear silently.
          clearStaleCase();
        } else {
          setError(e instanceof Error ? e.message : "Failed to load case");
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCaseId]);

  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const handleNewProject = async () => {
    const name = window.prompt("Name this project (e.g. patient name):");
    if (!name) return;
    try {
      setLoading(true);
      const proj = await createProject(name);
      setProjects((prev) => [proj, ...prev]);
      setSelectedProjectId(proj.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  const handleNewCase = async () => {
    if (!selectedModule || !selectedProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const sess = await createCase(selectedModule, {
        project_id: selectedProjectId,
      });
      // Kick off the workflow — engine runs until first pause/terminal.
      await executeWorkflow(
        { module_name: selectedModule, context: {} },
        sess.id,
      );
      const updated = await getCase(sess.id);
      setSelectedCaseId(sess.id);
      setActiveCase(updated);
      await refreshCases();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start case");
    } finally {
      setLoading(false);
    }
  };

  const handleProvideInput = async (inputs: Record<string, unknown>) => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    try {
      await provideInput(activeCase.id, inputs);
      const updated = await getCase(activeCase.id);
      setActiveCase(updated);
      await refreshCases();
    } catch (e) {
      if (isStaleCaseError(e)) {
        await clearStaleCase();
      } else if (isWrongStateError(e)) {
        // The case advanced past AWAITING_INPUT (double-submit, or
        // another tab moved it forward). Re-sync silently and let the
        // user see whichever step we're really on now.
        await resyncCase(activeCase.id);
      } else {
        setError(e instanceof Error ? e.message : "Failed to submit step");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCase = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      await deleteCase(id);
    } catch (e) {
      // 404 on delete is OK — it's already gone.
      if (!isStaleCaseError(e)) {
        setError(e instanceof Error ? e.message : "Failed to delete case");
      }
    } finally {
      // Always clear local state for the deleted id and refresh.
      if (selectedCaseId === id) {
        setSelectedCaseId(null);
        setActiveCase(null);
      }
      await refreshCases();
      setLoading(false);
    }
  };

  const handleRewind = async (nodeId: string) => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    try {
      await rewindCase(activeCase.id, nodeId);
      const updated = await getCase(activeCase.id);
      setActiveCase(updated);
      await refreshCases();
    } catch (e) {
      if (isStaleCaseError(e)) {
        await clearStaleCase();
      } else {
        setError(e instanceof Error ? e.message : "Failed to go back");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!activeCase) return;
    setLoading(true);
    setError(null);
    try {
      await approveSession(activeCase.id);
      const updated = await getCase(activeCase.id);
      setActiveCase(updated);
      await refreshCases();
    } catch (e) {
      if (isStaleCaseError(e)) {
        await clearStaleCase();
      } else if (isWrongStateError(e)) {
        await resyncCase(activeCase.id);
      } else {
        setError(e instanceof Error ? e.message : "Failed to approve step");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-6">
      {/* Left frame */}
      <CaseSidebar
        projects={projects}
        selectedProjectId={selectedProjectId}
        onSelectProject={(id) => {
          setSelectedProjectId(id);
          setSelectedCaseId(null);
          setActiveCase(null);
        }}
        onNewProject={handleNewProject}
        modules={modules}
        selectedModule={selectedModule}
        onSelectModule={(m) => {
          setSelectedModule(m);
          setSelectedCaseId(null);
          setActiveCase(null);
        }}
        cases={cases}
        selectedCaseId={selectedCaseId}
        onSelectCase={setSelectedCaseId}
        onNewCase={handleNewCase}
        onDeleteCase={handleDeleteCase}
        loading={loading}
      />

      {/* Middle frame */}
      <div className="space-y-4 min-h-[400px]">
        {error && (
          <div className="card border-l-4 border-l-[var(--color-danger)]">
            <p className="text-sm text-[var(--color-danger)]">
              <strong>Something went wrong.</strong> {error}
            </p>
            <button
              className="text-xs text-[var(--color-text-muted)] mt-2 hover:underline"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {!selectedProject && (
          <div className="card flex items-center justify-center min-h-[300px]">
            <p className="text-subtle text-center">
              Choose a project on the left, or create a new one to get started.
            </p>
          </div>
        )}

        {selectedProject && !activeCase && (
          <div className="card flex items-center justify-center min-h-[300px]">
            <p className="text-subtle text-center">
              {cases.length === 0
                ? "Pick a workflow on the left and click + New case to begin."
                : "Choose a case on the left, or click + New case to start another."}
            </p>
          </div>
        )}

        {activeCase && (
          <>
            <div className="card">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold">{activeCase.name}</h2>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5 font-mono">
                    {activeCase.module_name} · v{activeCase.module_version}
                  </p>
                </div>
                <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
                  {activeCase.id.slice(0, 8)}
                </span>
              </div>
            </div>

            <Stepper caseRecord={activeCase} onRewind={handleRewind} />

            <InformationSoFar caseRecord={activeCase} />

            <StepCard
              caseRecord={activeCase}
              loading={loading}
              onSubmit={handleProvideInput}
              onApprove={handleApprove}
            />

            <Documents caseRecord={activeCase} />
          </>
        )}
      </div>

      {/* Right frame */}
      <Concierge caseRecord={activeCase} />
    </div>
  );
}
