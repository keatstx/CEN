import { useCallback, useEffect, useState } from "react";

import {
  deleteSOP,
  extractSOP,
  listSOPs,
  parseSOP,
  promoteSOP,
  uploadSOP,
} from "../api";
import type { SOPRecord } from "../types";

export type UploadStage = "idle" | "uploading" | "parsing" | "extracting";

export interface SOPSession {
  sops: SOPRecord[];
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  selected: SOPRecord | null;
  busy: boolean;
  uploadStage: UploadStage;
  error: string | null;
  setError: (e: string | null) => void;
  handleUpload: (file: File) => Promise<void>;
  handleParse: (id: string) => Promise<void>;
  handleExtract: (id: string) => Promise<void>;
  handlePromote: (id: string, name?: string) => Promise<void>;
  handleDelete: (id: string) => Promise<void>;
  refresh: () => void;
  onModulePromoted?: () => void;
  setOnModulePromoted: (cb: (() => void) | undefined) => void;
}

/**
 * Single source of truth for the SOP Studio surface. Same lift-to-App
 * pattern as `useCaseSession` — the left rail's SOP sub-nav and the
 * center's review pane both read from this one hook.
 */
export function useSOPSession(): SOPSession {
  const [sops, setSops] = useState<SOPRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadStage, setUploadStage] = useState<UploadStage>("idle");
  const [refreshKey, setRefreshKey] = useState(0);
  const [onModulePromoted, setOnModulePromoted] = useState<(() => void) | undefined>();

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await listSOPs();
        if (!cancelled) setSops(list);
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const selected = sops.find((s) => s.id === selectedId) ?? null;

  const handleUpload = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    setUploadStage("uploading");
    try {
      const created = await uploadSOP(file);
      setUploadStage("parsing");
      await parseSOP(created.id);
      setUploadStage("extracting");
      await extractSOP(created.id);
      setSelectedId(created.id);
      refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      setUploadStage("idle");
    }
  }, [refresh]);

  const handleParse = useCallback(async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await parseSOP(id);
      refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const handleExtract = useCallback(async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await extractSOP(id);
      refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const handlePromote = useCallback(
    async (id: string, name?: string) => {
      setBusy(true);
      setError(null);
      try {
        await promoteSOP(id, name);
        refresh();
        onModulePromoted?.();
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [refresh, onModulePromoted],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      setBusy(true);
      setError(null);
      try {
        await deleteSOP(id);
        if (selectedId === id) setSelectedId(null);
        refresh();
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [selectedId, refresh],
  );

  return {
    sops,
    selectedId,
    setSelectedId,
    selected,
    busy,
    uploadStage,
    error,
    setError,
    handleUpload,
    handleParse,
    handleExtract,
    handlePromote,
    handleDelete,
    refresh,
    onModulePromoted,
    setOnModulePromoted,
  };
}
