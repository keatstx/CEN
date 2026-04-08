import type { Session } from "../types";

interface Props {
  caseRecord: Session;
}

/**
 * Compact horizontal stepper showing executed nodes plus the current
 * pending one. Sits above the StepCard in the middle frame to give
 * the user a sense of where they are in the workflow.
 *
 * Loops in the DAG can revisit nodes — that's intentional, the
 * stepper shows execution order, not graph topology.
 */
export default function Stepper({ caseRecord }: Props) {
  const executed = caseRecord.executed_nodes;
  const pending = caseRecord.pending_node;
  const isPaused =
    caseRecord.status === "AWAITING_INPUT" ||
    caseRecord.status === "AWAITING_APPROVAL";
  const isDone = caseRecord.status === "COMPLETED";

  type StepState = "done" | "current";
  const items: { id: string; state: StepState }[] = executed.map((id) => ({
    id,
    state: "done",
  }));
  if (isPaused && pending && !executed.includes(pending)) {
    items.push({ id: pending, state: "current" });
  }

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          Your progress
        </p>
        <p className="text-[10px] text-[var(--color-text-muted)]">
          {isDone
            ? `${executed.length} step${executed.length === 1 ? "" : "s"} complete`
            : `Step ${executed.length + (isPaused ? 1 : 0)}`}
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, idx) => (
          <div
            key={`${item.id}-${idx}`}
            className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] ${
              item.state === "current"
                ? "bg-[var(--color-warning-muted)] text-[var(--color-warning)] border border-[var(--color-warning)] font-semibold"
                : "bg-[var(--color-bg)] text-[var(--color-text-secondary)]"
            }`}
          >
            <span>{item.state === "done" ? "✓" : "▶"}</span>
            <span className="font-mono">{humanize(item.id)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function humanize(id: string): string {
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
