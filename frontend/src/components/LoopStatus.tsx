import type { Session } from "../types";

interface LoopState {
  iteration: number;
  status: string; // running | iterating | resolved | escalated
  exit_met: boolean;
  max_iterations: number;
  label: string;
}

// Plain-language status per §5 — no "iteration"/"escalated" in the UI.
const STATUS: Record<string, { text: string; bg: string; border: string }> = {
  running: { text: "In progress", bg: "rgba(59,130,246,0.12)", border: "rgb(59,130,246)" },
  iterating: { text: "In progress", bg: "rgba(59,130,246,0.12)", border: "rgb(59,130,246)" },
  resolved: { text: "Done", bg: "rgba(34,197,94,0.15)", border: "rgb(34,197,94)" },
  escalated: { text: "Sent to a specialist", bg: "rgba(234,179,8,0.15)", border: "rgb(234,179,8)" },
};

function collect(context: Record<string, unknown>): Array<[string, LoopState]> {
  const raw = context["__loop_state"];
  if (!raw || typeof raw !== "object") return [];
  return Object.entries(raw as Record<string, LoopState>).filter(
    ([, v]) => v && typeof v === "object",
  );
}

/**
 * Surfaces bounded-loop progress for the active case — how many rounds a
 * repeating step has run, and whether it finished or was sent to a
 * specialist when the round limit was reached. Reads context.__loop_state.
 */
export default function LoopStatus({ caseRecord }: { caseRecord: Session }) {
  const loops = collect(caseRecord.context);
  if (loops.length === 0) return null;
  return (
    <div className="card">
      <h3 className="text-sm font-semibold mb-2">Repeating steps</h3>
      <div className="space-y-2">
        {loops.map(([id, ls]) => {
          const s = STATUS[ls.status] || STATUS.running;
          // Rounds completed, capped at the limit for display.
          const done = Math.min(ls.iteration, ls.max_iterations);
          return (
            <div key={id} className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-medium truncate">{ls.label}</p>
                <p className="text-[11px] text-[var(--color-text-muted)]">
                  Round {done} of {ls.max_iterations}
                </p>
              </div>
              <span
                className="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded"
                style={{ background: s.bg, border: `1px solid ${s.border}`, color: "var(--color-text-secondary)" }}
              >
                {s.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
