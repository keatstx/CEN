import { useState } from "react";
import type { WorkflowResult } from "../types";
import NodeBadge from "./NodeBadge";

interface Props {
  result: WorkflowResult;
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

export default function ResultPanel({ result }: Props) {
  const [showContext, setShowContext] = useState(false);

  return (
    <div className="space-y-6 animate-fade-in">
      <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
        Execution Result
      </h3>

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
      <div className="rounded-lg bg-[var(--color-success-muted)] border border-[var(--color-success)]30 p-4">
        <p className="text-sm font-medium text-[var(--color-success)]">
          {result.final_outcome}
        </p>
      </div>

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
