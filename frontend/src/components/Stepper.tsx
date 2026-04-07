import type { Session } from "../types";

interface Props {
  caseRecord: Session;
}

/**
 * Compact horizontal stepper showing executed nodes and the current
 * pending node. Loops in the DAG can cause the same node to appear
 * twice — that's intentional, the stepper shows execution order, not
 * graph topology.
 */
export default function Stepper({ caseRecord }: Props) {
  const executed = caseRecord.executed_nodes;
  const pending = caseRecord.pending_node;
  const isPaused =
    caseRecord.status === "AWAITING_INPUT" ||
    caseRecord.status === "AWAITING_APPROVAL";

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
      <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-2">
        Progress
      </p>
      <div className="flex flex-wrap gap-1.5 text-[10px]">
        {items.map((item, idx) => (
          <div
            key={`${item.id}-${idx}`}
            className={`flex items-center gap-1 px-2 py-0.5 rounded ${
              item.state === "current"
                ? "bg-[var(--color-warning-muted)] text-[var(--color-warning)] border border-[var(--color-warning)]"
                : "bg-[var(--color-bg)] text-[var(--color-text-secondary)]"
            }`}
          >
            <span>
              {item.state === "done" ? "✓" : "▶"}
            </span>
            <span className="font-mono">{item.id}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
