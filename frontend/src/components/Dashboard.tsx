import { useEffect, useState } from "react";
import { fetchQueue } from "../api";
import type { BucketedQueue, QueueCase } from "../types";
import CaseCard from "./dashboard/CaseCard";
import MetricsStrip from "./dashboard/MetricsStrip";

interface Props {
  /** Called when the navigator clicks a case — App switches the
   * active tab to "executor" and pre-selects this case. */
  onCaseSelected: (caseId: string) => void;
  /** Bumped by App when the dashboard tab becomes active so we
   * re-fetch fresh data on tab focus. */
  refreshKey?: number;
}

/**
 * Navigator Dashboard — the new default landing page.
 *
 * Buckets the navigator's cases by attention-state. One click on a
 * card → land in the Executor with the case loaded. Server controls
 * the bucketing rules; this component just renders.
 */
export default function Dashboard({ onCaseSelected, refreshKey = 0 }: Props) {
  const [queue, setQueue] = useState<BucketedQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const q = await fetchQueue();
        if (!cancelled) setQueue(q);
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (loading && !queue) {
    return (
      <p className="text-sm text-[var(--color-text-muted)] italic">
        Loading your cases…
      </p>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ borderColor: "var(--color-danger)" }}>
        <p className="text-sm">
          We couldn't load your dashboard. {error}
        </p>
      </div>
    );
  }

  if (!queue) return null;

  const totalCases =
    queue.needs_attention.length +
    queue.waiting_external.length +
    queue.in_progress.length +
    queue.idle.length +
    queue.done_today.length +
    queue.failed.length;

  if (totalCases === 0) {
    return (
      <EmptyState />
    );
  }

  return (
    <div className="space-y-6">
      <MetricsStrip metrics={queue.metrics} />

      {queue.failed.length > 0 && (
        <FailedAlert cases={queue.failed} onSelect={onCaseSelected} />
      )}

      <BucketSection
        title="Needs your attention"
        subtitle="Cases waiting on your input or approval"
        cases={queue.needs_attention}
        onSelect={onCaseSelected}
        accent="var(--color-warning)"
      />

      <BucketSection
        title="Waiting on someone else"
        subtitle="Sent to specialist, awaiting response"
        cases={queue.waiting_external}
        onSelect={onCaseSelected}
        accent="var(--color-blue)"
      />

      <BucketSection
        title="In progress"
        subtitle="Currently running"
        cases={queue.in_progress}
        onSelect={onCaseSelected}
        accent="var(--color-blue)"
      />

      <BucketSection
        title="Gone idle"
        subtitle="Cases with no activity in 3+ days"
        cases={queue.idle}
        onSelect={onCaseSelected}
        accent="var(--color-warning)"
      />

      <BucketSection
        title="Done today"
        subtitle="Completed in the last 24 hours"
        cases={queue.done_today}
        onSelect={onCaseSelected}
        accent="var(--color-success)"
      />
    </div>
  );
}

function BucketSection({
  title,
  subtitle,
  cases,
  onSelect,
  accent,
}: {
  title: string;
  subtitle: string;
  cases: QueueCase[];
  onSelect: (id: string) => void;
  accent: string;
}) {
  if (cases.length === 0) return null;
  return (
    <section>
      <header className="mb-3 flex items-baseline justify-between">
        <div>
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: accent }}
            />
            {title}
            <span className="text-[var(--color-text-muted)] font-normal">
              ({cases.length})
            </span>
          </h2>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
            {subtitle}
          </p>
        </div>
      </header>
      <div className="space-y-2">
        {cases.map((c) => (
          <CaseCard key={c.id} caseRecord={c} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}

function FailedAlert({
  cases,
  onSelect,
}: {
  cases: QueueCase[];
  onSelect: (id: string) => void;
}) {
  return (
    <div
      className="card"
      style={{ borderColor: "var(--color-danger)" }}
    >
      <p className="text-sm font-semibold mb-2" style={{ color: "var(--color-danger)" }}>
        {cases.length === 1 ? "1 case stopped" : `${cases.length} cases stopped`}
      </p>
      <p className="text-xs text-[var(--color-text-secondary)] mb-2">
        These cases hit an error. Open them to see what went wrong and
        whether they can be resumed.
      </p>
      <div className="space-y-2">
        {cases.map((c) => (
          <CaseCard key={c.id} caseRecord={c} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="card text-center py-12">
      <p className="text-2xl mb-2" aria-hidden>
        👋
      </p>
      <h2 className="text-base font-semibold mb-1">Ready when you are</h2>
      <p className="text-sm text-[var(--color-text-secondary)]">
        You don't have any cases yet. Open the Executor tab to start your
        first one.
      </p>
    </div>
  );
}
