import type { Session } from "../types";

interface Props {
  caseRecord: Session | null;
}

/**
 * Right-frame AI Concierge placeholder. The full RAG-grounded chat UI
 * lands in step 6 of the foundation roadmap. For now, this is a quiet
 * card that establishes the layout and explains what's coming.
 */
export default function Concierge({ caseRecord }: Props) {
  return (
    <div className="card space-y-3 sticky top-6">
      <div className="flex items-center gap-2">
        <span
          className="inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: "var(--color-blue)" }}
        />
        <h3 className="text-sm font-semibold">AI Concierge</h3>
        <span className="text-[10px] font-mono text-[var(--color-text-muted)] ml-auto">
          Coming soon
        </span>
      </div>

      <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
        Ask any question about the current step in plain language and the
        AI assistant will answer using the project's reference FAQs. The
        chat interface lands in the next phase of development.
      </p>

      {caseRecord && (
        <div className="text-[11px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-3">
          <p className="font-medium mb-1">Current context</p>
          <p>Workflow: <span className="font-mono">{caseRecord.module_name}</span></p>
          {caseRecord.pending_node && (
            <p>Step: <span className="font-mono">{caseRecord.pending_node}</span></p>
          )}
        </div>
      )}

      <p className="text-[10px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-3 italic">
        The AI Concierge is for explaining workflow steps. It is not a
        lawyer, doctor, or financial advisor — it cannot give personalized
        legal, medical, or financial advice.
      </p>
    </div>
  );
}
