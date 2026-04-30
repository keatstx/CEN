import type { QueueCase } from "../../types";
import { STATUS_COLOR, STATUS_LABEL } from "../../lib/status";
import { dueLabel, relativeTime } from "../../lib/time";

interface Props {
  caseRecord: QueueCase;
  onSelect: (caseId: string) => void;
}

/**
 * Single dashboard row. One click drops the navigator into the
 * Executor with this case loaded. Compact by design — name, module,
 * status, pending step, due-soon badge, last-activity stamp.
 */
export default function CaseCard({ caseRecord: c, onSelect }: Props) {
  const statusLabel = STATUS_LABEL[c.status] ?? c.status;
  const statusColor = STATUS_COLOR[c.status] ?? "var(--color-text-muted)";

  return (
    <button
      type="button"
      onClick={() => onSelect(c.id)}
      className="w-full text-left card hover:bg-[var(--color-bg)] transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate">{c.name}</p>
          <p className="text-[11px] text-[var(--color-text-muted)] truncate">
            {c.module_name}
            {c.pending_node && ` · ${c.pending_node}`}
          </p>
        </div>
        <div className="flex flex-col items-end flex-shrink-0 gap-1">
          <span
            className="text-[10px] px-1.5 py-0.5 rounded font-medium uppercase tracking-wider"
            style={{
              background: `color-mix(in srgb, ${statusColor} 15%, transparent)`,
              color: statusColor,
            }}
          >
            {statusLabel}
          </span>
          {(c.is_overdue || c.is_due_soon) && (
            <DueBadge isOverdue={c.is_overdue} dueAt={c.due_at} />
          )}
        </div>
      </div>
      <div className="flex items-center justify-between mt-2 text-[10px] text-[var(--color-text-muted)]">
        <span>{relativeTime(c.last_activity_at)}</span>
        {c.days_idle >= 3 && (
          <span style={{ color: "var(--color-warning)" }}>
            Idle {c.days_idle}d
          </span>
        )}
      </div>
    </button>
  );
}

function DueBadge({
  isOverdue,
  dueAt,
}: {
  isOverdue: boolean;
  dueAt: string | null;
}) {
  const color = isOverdue ? "var(--color-danger)" : "var(--color-warning)";
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded font-medium"
      style={{
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
      }}
      title={dueAt ?? ""}
    >
      {dueLabel(dueAt)}
    </span>
  );
}
