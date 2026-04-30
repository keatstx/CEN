import { useEffect, useState } from "react";
import {
  deleteSOP,
  extractSOP,
  listSOPs,
  parseSOP,
  promoteSOP,
  uploadSOP,
} from "../api";
import type { SOPRecord, ValidationIssue } from "../types";

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
    try {
      const created = await uploadSOP(file);
      // Auto-advance through parse + extract so the author lands on the
      // review pane immediately. Errors here are recoverable (reload
      // the page, re-run the step from the row).
      await parseSOP(created.id);
      await extractSOP(created.id);
      setSelectedId(created.id);
      refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
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
        <UploadCard busy={busy} onUpload={handleUpload} />
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
          />
        )}
      </div>
    </div>
  );
}

// ── Subcomponents ──────────────────────────────────────────────

function UploadCard({
  busy,
  onUpload,
}: {
  busy: boolean;
  onUpload: (f: File) => void;
}) {
  const [dragOver, setDragOver] = useState(false);

  return (
    <div
      className={`card transition-colors ${
        dragOver ? "ring-2 ring-[var(--color-accent)]" : ""
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) onUpload(file);
      }}
    >
      <h3 className="text-sm font-semibold mb-2">Upload an SOP</h3>
      <p className="text-xs text-[var(--color-text-muted)] mb-3">
        Drop a Markdown (.md) or Word (.docx) file. We'll read it,
        pull out the steps, and show you a draft workflow you can
        review before promoting.
      </p>
      <label className="block">
        <input
          type="file"
          accept=".md,.markdown,.docx,.txt,text/markdown,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          disabled={busy}
          className="text-xs"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUpload(file);
            e.target.value = "";
          }}
        />
      </label>
      {busy && (
        <p className="mt-3 text-xs text-[var(--color-text-muted)]">
          Reading your SOP — this usually takes a few seconds…
        </p>
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
}: {
  sop: SOPRecord;
  busy: boolean;
  onParse: () => void;
  onExtract: () => void;
  onPromote: (name?: string) => void;
}) {
  const [moduleName, setModuleName] = useState("");
  const errors = sop.validation_issues.filter((i) => i.severity === "error");
  const warnings = sop.validation_issues.filter((i) => i.severity === "warning");
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
              <button
                className="btn-secondary text-xs"
                disabled={busy}
                onClick={onParse}
              >
                Read this SOP
              </button>
            )}
            {(sop.status === "parsed" || sop.status === "extracted") && (
              <button
                className="btn-secondary text-xs"
                disabled={busy}
                onClick={onExtract}
              >
                Re-extract draft
              </button>
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
          <ValidationSummary errors={errors} warnings={warnings} />
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
                <button
                  className="btn-primary text-xs"
                  disabled={busy || hasBlocker}
                  onClick={() => onPromote(moduleName.trim() || undefined)}
                >
                  Promote
                </button>
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

function ValidationSummary({
  errors,
  warnings,
}: {
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}) {
  if (errors.length === 0 && warnings.length === 0) {
    return (
      <div className="card" style={{ borderColor: "var(--color-success)" }}>
        <p className="text-sm">
          ✓ The draft looks clean — no issues found.
        </p>
      </div>
    );
  }
  return (
    <div className="card space-y-2">
      <h3 className="text-sm font-semibold">
        Review notes
        <span className="ml-2 text-xs text-[var(--color-text-muted)] font-normal">
          {errors.length} {errors.length === 1 ? "issue" : "issues"} to fix,{" "}
          {warnings.length} {warnings.length === 1 ? "warning" : "warnings"}
        </span>
      </h3>
      <ul className="space-y-1 text-xs">
        {errors.map((i, idx) => (
          <li key={`e-${idx}`} style={{ color: "var(--color-error)" }}>
            • {i.node_id ? <code>{i.node_id}</code> : "—"}: {i.message}
          </li>
        ))}
        {warnings.map((i, idx) => (
          <li key={`w-${idx}`} style={{ color: "var(--color-warning, #b45309)" }}>
            • {i.node_id ? <code>{i.node_id}</code> : "—"}: {i.message}
          </li>
        ))}
      </ul>
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
