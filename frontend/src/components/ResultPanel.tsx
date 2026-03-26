import { useState } from "react";
import type { Session, WorkflowResult } from "../types";
import NodeBadge from "./NodeBadge";

interface Props {
  result: WorkflowResult;
  session: Session | null;
  loading: boolean;
  onApprove: () => void;
}

function inferNodeType(nodeId: string, result: WorkflowResult): string {
  if (
    result.final_outcome.startsWith("handoff:") &&
    nodeId === result.executed_nodes[result.executed_nodes.length - 1]
  ) {
    return "HANDOFF";
  }
  if (result.context[`${nodeId}_result`] !== undefined) {
    return "CONDITION";
  }
  return "ACTION";
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  ACTIVE: {
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    label: "Active",
  },
  AWAITING_APPROVAL: {
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    label: "Awaiting Approval",
  },
  COMPLETED: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    label: "Completed",
  },
  FAILED: {
    bg: "bg-red-500/10",
    text: "text-red-400",
    label: "Failed",
  },
};

export default function ResultPanel({ result, session, loading, onApprove }: Props) {
  const [showContext, setShowContext] = useState(false);

  const isPendingApproval = result.final_outcome.startsWith("pending_approval:");
  const pendingGateLabel = isPendingApproval
    ? result.final_outcome.replace("pending_approval:", "").trim()
    : null;

  const statusInfo = session ? STATUS_STYLES[session.status] : null;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          Execution Result
        </h3>
        {statusInfo && (
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${statusInfo.bg} ${statusInfo.text}`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            {statusInfo.label}
          </span>
        )}
      </div>

      {/* Node flow */}
      <div className="flex flex-wrap items-center gap-2">
        {result.executed_nodes.map((nodeId, i) => (
          <div key={nodeId} className="flex items-center gap-2">
            {i > 0 && (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-[var(--color-text-muted)]">
                <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            <NodeBadge nodeId={nodeId} nodeType={inferNodeType(nodeId, result)} />
          </div>
        ))}
      </div>

      {/* Final outcome */}
      {isPendingApproval ? (
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-4 space-y-3">
          <p className="text-sm font-medium text-amber-400">
            Workflow paused — awaiting approval at gate:{" "}
            <span className="font-semibold">{pendingGateLabel}</span>
          </p>
          <button
            type="button"
            onClick={onApprove}
            disabled={loading}
            className="bg-amber-500 hover:bg-amber-400 text-black text-sm font-medium px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Approving…
              </span>
            ) : (
              "Approve & Continue"
            )}
          </button>
        </div>
      ) : (
        <div className="rounded-lg bg-[var(--color-success-muted)] border border-[var(--color-success)]/20 p-4">
          <p className="text-sm font-medium text-[var(--color-success)]">
            {result.final_outcome}
          </p>
        </div>
      )}

      {/* Context viewer */}
      <div>
        <button
          type="button"
          onClick={() => setShowContext(!showContext)}
          className="text-xs text-[var(--color-accent)] hover:text-[var(--color-accent-hover)] transition-colors cursor-pointer"
          style={{ background: "none", border: "none", padding: 0, boxShadow: "none" }}
        >
          {showContext ? "▾ Hide" : "▸ Show"} execution context
        </button>
        {showContext && (
          <pre className="mt-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4 text-xs overflow-x-auto max-h-80 overflow-y-auto text-[var(--color-text-secondary)] font-mono leading-relaxed animate-fade-in">
            {JSON.stringify(result.context, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
