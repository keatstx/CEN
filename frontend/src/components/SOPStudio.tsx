import { useEffect, useState } from "react";
import {
  deleteSOP,
  extractSOP,
  listSOPs,
  parseSOP,
  promoteSOP,
  uploadSOP,
  type DraftEditResponse,
} from "../api";
import type { SOPRecord } from "../types";
import Button from "./ui/Button";
import Spinner from "./ui/Spinner";
import ValidationPanel from "./sop/ValidationPanel";

interface Props {
  onModulePromoted?: () => void;
}

const STATUS_LABELS: Record<SOPRecord["status"], string> = {
  uploaded: "Uploaded — needs parsing",
  parsed: "Parsed — needs extraction",
  extracted: "Draft ready for review",
  promoted: "Promoted to a workflow",
  failed: "Couldn't read this file",
};

const STATUS_COLORS: Record<SOPRecord["status"], string> = {
  uploaded: "var(--color-text-muted)",
  parsed: "var(--color-text-secondary)",
  extracted: "var(--color-accent)",
  promoted: "var(--color-success)",
  failed: "var(--color-error)",
};

export default function SOPStudio({ onModulePromoted }: Props) {
  const [sops, setSops] = useState<SOPRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  // Upload runs three sequential server calls (upload, parse, extract).
  // Track which stage we're in so the user sees real progress, not
  // a single "loading" spinner that lasts 5+ seconds with no signal.
  const [uploadStage, setUploadStage] =
    useState<"idle" | "uploading" | "parsing" | "extracting">("idle");

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

  const refresh = () => setRefreshKey((k) => k + 1);

  const selected = sops.find((s) => s.id === selectedId) ?? null;

  const handleUpload = async (file: File) => {
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
  };

  const handleParse = async (id: string) => {
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
  };

  const handleExtract = async (id: string) => {
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
  };

  const handlePromote = async (id: string, name?: string) => {
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
  };

  const handleDelete = async (id: string) => {
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
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
      {/* Left — uploader + list */}
      <div className="lg:col-span-2 space-y-6">
        <UploadCard busy={busy} uploadStage={uploadStage} onUpload={handleUpload} />
        <SOPList
          sops={sops}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={handleDelete}
        />
      </div>

      {/* Right — review pane */}
      <div className="lg:col-span-3">
        {error && (
          <div
            className="card border-[var(--color-error)] mb-4"
            style={{ borderColor: "var(--color-error)" }}
          >
            <p className="text-sm">{error}</p>
          </div>
        )}
        {!selected ? (
          <EmptyReview hasUploads={sops.length > 0} />
        ) : (
          <ReviewPane
            sop={selected}
            busy={busy}
            onParse={() => handleParse(selected.id)}
            onExtract={() => handleExtract(selected.id)}
            onPromote={(name) => handlePromote(selected.id, name)}
            onDraftUpdated={() => refresh()}
          />
        )}
      </div>
    </div>
  );
}

// ── Subcomponents ──────────────────────────────────────────────

function UploadCard({
  busy,
  uploadStage,
  onUpload,
}: {
  busy: boolean;
  uploadStage: "idle" | "uploading" | "parsing" | "extracting";
  onUpload: (f: File) => void;
}) {
  const [dragOver, setDragOver] = useState(false);

  const stageLabel: Record<typeof uploadStage, string> = {
    idle: "",
    uploading: "Uploading…",
    parsing: "Reading the document…",
    extracting: "Extracting steps…",
  };

  const handleFile = (file: File) => {
    onUpload(file);
  };

  return (
    <div
      className={`card transition-colors ${
        dragOver ? "ring-2 ring-[var(--color-accent)]" : ""
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!busy) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        if (busy) return;
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
      }}
    >
      <h3 className="text-sm font-semibold mb-2">Upload an SOP</h3>
      <p className="text-xs text-[var(--color-text-muted)] mb-3">
        Drop a Markdown (.md) or Word (.docx) file here, or click the
        button below. We'll read it, pull out the steps, and show you
        a draft workflow you can review before promoting.
      </p>

      {/* The visible button — actually a label that opens the hidden
          file input. Real button styling, real hover state. */}
      <label
        htmlFor="sop-file-input"
        className="inline-flex items-center justify-center gap-1.5 rounded font-medium transition-colors border text-xs px-3 py-1.5 cursor-pointer"
        style={{
          background: busy ? "var(--color-bg)" : "var(--color-accent)",
          color: busy ? "var(--color-text-muted)" : "white",
          borderColor: busy ? "var(--color-border)" : "var(--color-accent)",
          opacity: busy ? 0.6 : 1,
          cursor: busy ? "not-allowed" : "pointer",
          pointerEvents: busy ? "none" : "auto",
        }}
        aria-disabled={busy}
      >
        {busy && <Spinner size={13} />}
        {busy ? "Working…" : "Choose a file"}
      </label>
      <input
        id="sop-file-input"
        type="file"
        accept=".md,.markdown,.docx,.txt,text/markdown,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disabled={busy}
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />

      {/* Multi-stage progress — the user sees real movement instead
          of a single spinner that lasts forever. */}
      {busy && uploadStage !== "idle" && (
        <div className="mt-3 flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
          <Spinner size={12} />
          <span>{stageLabel[uploadStage]}</span>
        </div>
      )}
    </div>
  );
}

function SOPList({
  sops,
  selectedId,
  onSelect,
  onDelete,
}: {
  sops: SOPRecord[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (sops.length === 0) {
    return (
      <div className="card">
        <p className="text-xs text-[var(--color-text-muted)]">
          No SOPs uploaded yet.
        </p>
      </div>
    );
  }
  return (
    <div className="card p-0 overflow-hidden">
      <div className="border-b border-[var(--color-border)] px-3 py-2">
        <h3 className="text-sm font-semibold">Your SOPs</h3>
      </div>
      <ul className="divide-y divide-[var(--color-border)]">
        {sops.map((s) => (
          <li
            key={s.id}
            className={`px-3 py-2 cursor-pointer hover:bg-[var(--color-bg)] ${
              s.id === selectedId ? "bg-[var(--color-bg)]" : ""
            }`}
            onClick={() => onSelect(s.id)}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{s.filename}</p>
                <p
                  className="text-[11px]"
                  style={{ color: STATUS_COLORS[s.status] }}
                >
                  {STATUS_LABELS[s.status]}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Delete ${s.filename}?`)) onDelete(s.id);
                }}
                className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-error)]"
                title="Delete this SOP"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EmptyReview({ hasUploads }: { hasUploads: boolean }) {
  return (
    <div className="card text-center py-12">
      <p className="text-sm text-[var(--color-text-secondary)]">
        {hasUploads
          ? "Pick an SOP from the list to review the draft workflow."
          : "Upload an SOP on the left to get started."}
      </p>
    </div>
  );
}

function ReviewPane({
  sop,
  busy,
  onParse,
  onExtract,
  onPromote,
  onDraftUpdated,
}: {
  sop: SOPRecord;
  busy: boolean;
  onParse: () => void;
  onExtract: () => void;
  onPromote: (name?: string) => void;
  onDraftUpdated: (updated: DraftEditResponse) => void;
}) {
  const [moduleName, setModuleName] = useState("");
  const errors = sop.validation_issues.filter((i) => i.severity === "error");
  const hasBlocker = errors.length > 0;

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{sop.filename}</h2>
            <p
              className="text-xs mt-1"
              style={{ color: STATUS_COLORS[sop.status] }}
            >
              {STATUS_LABELS[sop.status]}
            </p>
          </div>
          <div className="flex gap-2">
            {sop.status === "uploaded" && (
              <Button
                variant="secondary"
                loading={busy}
                loadingLabel="Reading…"
                onClick={onParse}
              >
                Read this SOP
              </Button>
            )}
            {(sop.status === "parsed" || sop.status === "extracted") && (
              <Button
                variant="secondary"
                loading={busy}
                loadingLabel="Re-extracting…"
                onClick={onExtract}
              >
                Re-extract draft
              </Button>
            )}
          </div>
        </div>
      </div>

      {sop.status === "promoted" && (
        <div className="card" style={{ borderColor: "var(--color-success)" }}>
          <p className="text-sm">
            ✓ Promoted as <code>{sop.promoted_module_name}</code> v
            {sop.promoted_module_version}. Open the DAG Viewer tab to see
            it.
          </p>
        </div>
      )}

      {sop.draft_module && (
        <>
          <ValidationPanel sop={sop} onDraftUpdated={onDraftUpdated} />
          <NodeTable nodes={sop.draft_module.nodes} />
          {sop.status === "extracted" && (
            <div className="card">
              <h3 className="text-sm font-semibold mb-2">Promote to a workflow</h3>
              <p className="text-xs text-[var(--color-text-muted)] mb-3">
                When you're happy with the draft, give it a name (lowercase
                letters, digits, underscores) and we'll register it as a
                live workflow you can run from the Executor.
              </p>
              {hasBlocker && (
                <p
                  className="text-xs mb-3"
                  style={{ color: "var(--color-error)" }}
                >
                  Fix the errors above before you can promote.
                </p>
              )}
              <div className="flex gap-2 items-center">
                <input
                  type="text"
                  placeholder={sop.draft_module.module_name}
                  value={moduleName}
                  onChange={(e) => setModuleName(e.target.value)}
                  className="flex-1 px-2 py-1 text-sm border border-[var(--color-border)] rounded"
                />
                <Button
                  loading={busy}
                  loadingLabel="Promoting…"
                  disabled={hasBlocker}
                  onClick={() => onPromote(moduleName.trim() || undefined)}
                >
                  Promote
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {sop.canonical_md && (
        <details className="card">
          <summary className="cursor-pointer text-sm font-semibold">
            Source markdown ({sop.canonical_md.length.toLocaleString()} chars)
          </summary>
          <pre className="mt-2 max-h-80 overflow-auto text-[11px] whitespace-pre-wrap text-[var(--color-text-secondary)]">
            {sop.canonical_md}
          </pre>
        </details>
      )}
    </div>
  );
}

function NodeTable({ nodes }: { nodes: import("../types").AOPNode[] }) {
  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          Draft workflow ({nodes.length} {nodes.length === 1 ? "step" : "steps"})
        </h3>
      </div>
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full text-xs">
          <thead className="bg-[var(--color-bg)] sticky top-0">
            <tr>
              <th className="text-left px-3 py-2 font-medium">ID</th>
              <th className="text-left px-3 py-2 font-medium">Type</th>
              <th className="text-left px-3 py-2 font-medium">Step</th>
              <th className="text-left px-3 py-2 font-medium">Actor</th>
              <th className="text-left px-3 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {nodes.map((n) => (
              <tr key={n.id} className="hover:bg-[var(--color-bg)]">
                <td className="px-3 py-2 font-mono">{n.id}</td>
                <td className="px-3 py-2">{n.type}</td>
                <td className="px-3 py-2">{n.metadata.label}</td>
                <td className="px-3 py-2 text-[var(--color-text-muted)]">
                  {n.metadata.actor || "—"}
                </td>
                <td className="px-3 py-2 text-[var(--color-text-muted)] truncate max-w-[200px]">
                  {n.metadata.source_ref?.section || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
