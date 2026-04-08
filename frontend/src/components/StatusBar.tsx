import type { ReadyResponse } from "../types";

interface Props {
  ready: ReadyResponse | null;
  error: string | null;
}

export default function StatusBar({ ready, error }: Props) {
  if (error) {
    return (
      <div className="border-b border-[var(--color-border)] bg-[var(--color-danger-muted)] px-6 py-2 text-xs text-[var(--color-danger)] flex items-center gap-2">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-danger)]" />
        Backend unreachable: {error}
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="border-b border-[var(--color-border)] px-6 py-2 text-xs text-[var(--color-text-muted)]">
        Connecting to backend…
      </div>
    );
  }

  return (
    <div className="border-b border-[var(--color-border)] px-6 py-2 text-xs flex items-center gap-4 text-[var(--color-text-secondary)]">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-success)] dot-pulse" />
      <span>{ready.modules_loaded.length} modules loaded</span>
      <span className="text-[var(--color-text-muted)]">·</span>
      <span>LLM: <span className="text-[var(--color-blue)]">{ready.llm_backend}</span></span>
      <span className="text-[var(--color-text-muted)]">·</span>
      <span>Status: <span className="text-[var(--color-success)]">{ready.status}</span></span>
    </div>
  );
}
