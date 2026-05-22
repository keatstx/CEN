import { useEffect, useState } from "react";
import {
  type DraftEditResponse,
} from "../api";
import type { SOPRecord } from "../types";
import type { SOPSession } from "../hooks/useSOPSession";
import Button from "./ui/Button";
import DraftDAG from "./sop/DraftDAG";
import ValidationPanel from "./sop/ValidationPanel";

interface Props {
  session: SOPSession;
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

export default function SOPStudio({ session, onModulePromoted }: Props) {
  const {
    sops,
    selected,
    busy,
    error,
    handleParse,
    handleExtract,
    handlePromote,
    refresh,
    setOnModulePromoted,
  } = session;

  // Wire the parent's onModulePromoted callback into the hook so
  // promote can fire it (refreshes the modules list in DAGViewer etc).
  useEffect(() => {
    setOnModulePromoted(() => onModulePromoted);
    return () => setOnModulePromoted(undefined);
  }, [onModulePromoted, setOnModulePromoted]);

  return (
    <div>
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
  );
}

// ── Subcomponents ──────────────────────────────────────────────

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
  // Selection shared between the DAG canvas and the validation panel —
  // click a node on the DAG to jump to its issues, click an issue to
  // highlight its node on the DAG (TODO: wire panel-side highlight).
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
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
          <DraftDAG
            draft={sop.draft_module}
            issues={sop.validation_issues}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
          />
          <ValidationPanel
            sop={sop}
            onDraftUpdated={onDraftUpdated}
            highlightNodeId={selectedNodeId}
            onSelectIssue={setSelectedNodeId}
          />
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
