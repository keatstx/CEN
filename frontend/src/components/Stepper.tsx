import type { Session } from "../types";

interface Props {
  caseRecord: Session;
  onRewind?: (nodeId: string) => void;
}

/**
 * Compact horizontal stepper showing executed nodes plus the current
 * pending one. Sits above the StepCard in the middle frame to give
 * the user a sense of where they are in the workflow.
 *
 * Executed steps are clickable — clicking one rewinds the workflow
 * to that step so the navigator can edit a prior answer. The current
 * step (yellow pill) is not clickable.
 *
 * Loops in the DAG can revisit nodes — that's intentional, the
 * stepper shows execution order, not graph topology.
 */
export default function Stepper({ caseRecord, onRewind }: Props) {
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

  const handleRewindClick = (nodeId: string) => {
    if (!onRewind) return;
    if (
      window.confirm(
        `Go back to "${humanize(nodeId)}"?\n\nYour current answer for this step ` +
          `(and any answers from steps that came after) will be cleared so you ` +
          `can re-enter them. Files you uploaded stay attached.`,
      )
    ) {
      onRewind(nodeId);
    }
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          Your progress {onRewind && "· click a step to go back"}
        </p>
        <p className="text-[10px] text-[var(--color-text-muted)]">
          {isDone
            ? `${executed.length} step${executed.length === 1 ? "" : "s"} complete`
            : `Step ${executed.length + (isPaused ? 1 : 0)}`}
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, idx) => {
          const baseClass = `flex items-center gap-1 px-2 py-1 rounded text-[10px] transition-colors`;
          if (item.state === "current") {
            return (
              <div
                key={`${item.id}-${idx}`}
                className={`${baseClass} bg-[var(--color-warning-muted)] text-[var(--color-warning)] border border-[var(--color-warning)] font-semibold`}
              >
                <span>▶</span>
                <span className="font-mono">{humanize(item.id)}</span>
              </div>
            );
          }
          return (
            <button
              key={`${item.id}-${idx}`}
              type="button"
              onClick={() => handleRewindClick(item.id)}
              disabled={!onRewind}
              title={
                onRewind
                  ? `Go back to "${humanize(item.id)}"`
                  : undefined
              }
              className={`${baseClass} bg-[var(--color-bg)] text-[var(--color-text-secondary)] ${
                onRewind
                  ? "hover:bg-[var(--color-accent)] hover:text-white cursor-pointer"
                  : ""
              }`}
            >
              <span>✓</span>
              <span className="font-mono">{humanize(item.id)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function humanize(id: string): string {
  return id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
