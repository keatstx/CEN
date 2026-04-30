import type { QueueMetrics } from "../../types";

interface Props {
  metrics: QueueMetrics;
}

/**
 * Four-number daily strip at the top of the Dashboard. Glanceable —
 * not a focus, just orientation for the navigator on what their day
 * has looked like so far.
 */
export default function MetricsStrip({ metrics }: Props) {
  const items: { label: string; value: number; tone?: string }[] = [
    { label: "Opened today", value: metrics.opened_today },
    { label: "Approvals today", value: metrics.approvals_today },
    { label: "Completed today", value: metrics.completed_today, tone: "success" },
    { label: "Open cases", value: metrics.open_cases },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {items.map((m) => (
        <div
          key={m.label}
          className="card py-3"
          style={{ minHeight: "auto" }}
        >
          <p className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] font-medium">
            {m.label}
          </p>
          <p
            className="text-2xl font-semibold mt-0.5"
            style={{
              color:
                m.tone === "success"
                  ? "var(--color-success)"
                  : "var(--color-text-primary)",
            }}
          >
            {m.value}
          </p>
        </div>
      ))}
    </div>
  );
}
