import { useState } from "react";
import type { ConciergeCitation } from "../../api";

/**
 * Sources behind one assistant reply, collapsed by default.
 *
 * Provenance is a non-negotiable (CLAUDE.md #6/#9) — a navigator has to
 * be able to check what an answer was built from before acting on it.
 * But rendering every citation inline turned the rail into a wall of
 * background text: three to five lines of step labels and verbatim FAQ
 * questions under each reply, pushing the actual answer off-screen.
 *
 * So the sources stay, one tap away, behind a count. The answer reads
 * clean; verification is still one click, never a round-trip.
 */
export default function CitationList({
  citations,
}: {
  citations: ConciergeCitation[];
}) {
  const [open, setOpen] = useState(false);

  if (citations.length === 0) return null;

  const fromStep = citations.filter((c) => c.from_step).length;

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
        title={
          open
            ? "Hide what this answer was based on"
            : "Show what this answer was based on"
        }
      >
        <span
          aria-hidden="true"
          className="inline-block transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        >
          ›
        </span>
        {open ? "Hide sources" : `${citations.length} source${citations.length === 1 ? "" : "s"}`}
        {!open && fromStep > 0 && (
          <span className="text-[var(--color-text-muted)] opacity-70">
            · {fromStep} from this step
          </span>
        )}
      </button>

      {open && (
        <div className="mt-1 space-y-0.5">
          {citations.map((c, idx) => (
            <CitationLine key={idx} citation={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function CitationLine({ citation }: { citation: ConciergeCitation }) {
  const tag =
    citation.kind === "workflow"
      ? "Step"
      : citation.kind === "sop"
      ? "SOP"
      : citation.kind === "case_context"
      ? "Case"
      : "FAQ";
  return (
    <div className="text-[10px] text-[var(--color-text-muted)] truncate">
      <span
        className="inline-block px-1 mr-1 rounded text-[9px] font-mono"
        style={{
          background: "var(--color-bg)",
          border: "1px solid var(--color-border)",
        }}
      >
        {tag}
      </span>
      {citation.from_step && (
        <span
          className="inline-block px-1 mr-1 rounded text-[9px] font-medium"
          style={{
            background: "rgba(34,197,94,0.15)",
            border: "1px solid rgb(34,197,94)",
            color: "var(--color-text-secondary)",
          }}
          title="This answer came from a FAQ scoped to the step you're on"
        >
          From this step
        </span>
      )}
      <span className="italic">{citation.question}</span>
    </div>
  );
}
