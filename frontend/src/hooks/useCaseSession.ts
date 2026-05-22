import { useCallback, useEffect, useMemo, useState } from "react";

import {
  approveSession,
  createCase,
  createProject,
  deleteCase,
  executeWorkflow,
  fetchSuggestions,
  getCase,
  listCases,
  listProjects,
  provideInput,
  rewindCase,
  type SuggestedInput,
} from "../api";
import type { Project, Session } from "../types";

/**
 * Single source of truth for the case-management surface (Project /
 * Workflow / Cases). Lives at App level so both the LeftNav sub-nav
 * (selectors) AND the Executor center (activity) can read & mutate
 * the same state without prop-drilling through multiple layers.
 *
 * Extracted from Executor.tsx so that:
 * - LeftNav can render Project/Workflow/Cases as sub-items
 * - Executor's center becomes a thin renderer over `activeCase`
 * - Concierge actions can drive selections (e.g. "Open case X" button
 *   that fires this hook's `setSelectedCaseId` to swap context)
 */
export interface CaseSession {
  projects: Project[];
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;

  selectedModule: string;
  setSelectedModule: (m: string) => void;

  cases: Session[];
  selectedCaseId: string | null;
  setSelectedCaseId: (id: string | null) => void;

  activeCase: Session | null;
  suggestions: SuggestedInput[];
  setSuggestions: React.Dispatch<React.SetStateAction<SuggestedInput[]>>;

  loading: boolean;
  error: string | null;
  setError: (e: string | null) => void;

  handleNewProject: () => Promise<void>;
  handleNewCase: () => Promise<void>;
  handleDeleteCase: (id: string) => Promise<void>;
  handleProvideInput: (inputs: Record<string, unknown>) => Promise<void>;
  handleApprove: () => Promise<void>;
  handleRewind: (nodeId: string) => Promise<void>;
  refreshCases: () => Promise<void>;
}

function isStaleCaseError(e: unknown): boolean {
  if (e instanceof Error) {
    const status = (e as Error & { status?: number }).status;
    if (status === 404) return true;
  }
  const msg = e instanceof Error ? e.message : String(e);
  return /not found/i.test(msg);
}

function isWrongStateError(e: unknown): boolean {
  if (e instanceof Error) {
    const status = (e as Error & { status?: number }).status;
    if (status === 409) return true;
  }
  return false;
}

export function useCaseSession(): CaseSession {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectIdState] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState("");
  const [cases, setCases] = useState<Session[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeCase, setActiveCase] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestedInput[]>([]);

  // Wrapper that clears case selection when project changes — keeps
  // the activeCase coherent with the chosen project.
  const setSelectedProjectId = useCallback((id: string | null) => {
    setSelectedProjectIdState(id);
    setSelectedCaseId(null);
    setActiveCase(null);
  }, []);

  // Load projects on mount; auto-select first.
  useEffect(() => {
    listProjects()
      .then((p) => {
        setProjects(p);
        if (p.length > 0) {
          setSelectedProjectIdState((prev) => prev ?? p[0].id);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const refreshCases = useCallback(async () => {
    if (!selectedProjectId) {
      setCases([]);
      return;
    }
    try {
      const list = await listCases({ project_id: selectedProjectId, limit: 100 });
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
    let cancelled = false;
    getCase(selectedCaseId)
      .then((c) => {
        if (!cancelled) setActiveCase(c);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        if (isStaleCaseError(e)) {
          setSelectedCaseId(null);
          setActiveCase(null);
          refreshCases();
        } else {
          setError(e.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCaseId, refreshCases]);

  // Refresh suggestions when the active case or its pending node changes.
  const activeCaseId = activeCase?.id ?? null;
  const pendingNode = activeCase?.pending_node ?? null;
  useEffect(() => {
    let cancelled = false;
    if (!activeCaseId) {
      setSuggestions([]);
      return;
    }
    fetchSuggestions(activeCaseId)
      .then((s) => {
        if (!cancelled) setSuggestions(s);
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeCaseId, pendingNode]);

  const clearStale = useCallback(async () => {
    setSelectedCaseId(null);
    setActiveCase(null);
    await refreshCases();
  }, [refreshCases]);

  const resyncCase = useCallback(
    async (id: string) => {
      try {
        const fresh = await getCase(id);
        setActiveCase(fresh);
        await refreshCases();
      } catch {
        await clearStale();
      }
    },
    [clearStale, refreshCases],
  );

  const handleNewProject = useCallback(async () => {
    const name = window.prompt("Name this project (e.g. patient name):");
    if (!name) return;
    try {
      setLoading(true);
      const proj = await createProject(name);
      setProjects((prev) => [proj, ...prev]);
      setSelectedProjectIdState(proj.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleNewCase = useCallback(async () => {
    if (!selectedModule || !selectedProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const sess = await createCase(selectedModule, {
        project_id: selectedProjectId,
      });
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
  }, [selectedModule, selectedProjectId, refreshCases]);

  const handleDeleteCase = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      try {
        await deleteCase(id);
      } catch (e) {
        if (!isStaleCaseError(e)) {
          setError(e instanceof Error ? e.message : "Failed to delete case");
        }
      } finally {
        if (selectedCaseId === id) {
          setSelectedCaseId(null);
          setActiveCase(null);
        }
        await refreshCases();
        setLoading(false);
      }
    },
    [selectedCaseId, refreshCases],
  );

  const handleProvideInput = useCallback(
    async (inputs: Record<string, unknown>) => {
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
          await clearStale();
        } else if (isWrongStateError(e)) {
          await resyncCase(activeCase.id);
        } else {
          setError(e instanceof Error ? e.message : "Failed to submit step");
        }
      } finally {
        setLoading(false);
      }
    },
    [activeCase, refreshCases, clearStale, resyncCase],
  );

  const handleApprove = useCallback(async () => {
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
        await clearStale();
      } else if (isWrongStateError(e)) {
        await resyncCase(activeCase.id);
      } else {
        setError(e instanceof Error ? e.message : "Failed to approve step");
      }
    } finally {
      setLoading(false);
    }
  }, [activeCase, refreshCases, clearStale, resyncCase]);

  const handleRewind = useCallback(
    async (nodeId: string) => {
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
          await clearStale();
        } else {
          setError(e instanceof Error ? e.message : "Failed to go back");
        }
      } finally {
        setLoading(false);
      }
    },
    [activeCase, refreshCases, clearStale],
  );

  return useMemo(
    () => ({
      projects,
      selectedProjectId,
      setSelectedProjectId,
      selectedModule,
      setSelectedModule,
      cases,
      selectedCaseId,
      setSelectedCaseId,
      activeCase,
      suggestions,
      setSuggestions,
      loading,
      error,
      setError,
      handleNewProject,
      handleNewCase,
      handleDeleteCase,
      handleProvideInput,
      handleApprove,
      handleRewind,
      refreshCases,
    }),
    [
      projects,
      selectedProjectId,
      setSelectedProjectId,
      selectedModule,
      cases,
      selectedCaseId,
      activeCase,
      suggestions,
      loading,
      error,
      handleNewProject,
      handleNewCase,
      handleDeleteCase,
      handleProvideInput,
      handleApprove,
      handleRewind,
      refreshCases,
    ],
  );
}
