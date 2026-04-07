import type { ReadyResponse } from "../types";

interface Props {
  ready: ReadyResponse | null;
  error: string | null;
}

function SyntheticBanner() {
  return (
    <div
      className="border-b-2 px-6 py-2 text-xs font-semibold flex items-center justify-center gap-2"
      style={{
        background: "#FEF3C7",
        borderColor: "#D97706",
        color: "#92400E",
      }}
    >
      <span aria-hidden>⚠</span>
      <span>
        SYNTHETIC DATA ONLY — This deployment is for development and testing.
        Do not enter or upload real patient information (PHI).
      </span>
    </div>
  );
}

export default function StatusBar({ ready, error }: Props) {
  if (error) {
    return (
      <>
        <SyntheticBanner />
        <div className="border-b border-[var(--color-border)] bg-[var(--color-danger-muted)] px-6 py-2 text-xs text-[var(--color-danger)] flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-danger)]" />
          Backend unreachable: {error}
        </div>
      </>
    );
  }

  if (!ready) {
    return (
      <>
        <SyntheticBanner />
        <div className="border-b border-[var(--color-border)] px-6 py-2 text-xs text-[var(--color-text-muted)]">
          Connecting to backend…
        </div>
      </>
    );
  }

  // Only show the synthetic banner when the backend confirms it.
  // In `production` mode (post-hardening) the banner disappears.
  const showBanner = ready.deployment_mode !== "production";

  return (
    <>
      {showBanner && <SyntheticBanner />}
      <div className="border-b border-[var(--color-border)] px-6 py-2 text-xs flex items-center gap-4 text-[var(--color-text-secondary)]">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-success)] dot-pulse" />
        <span>{ready.modules_loaded.length} modules loaded</span>
        <span className="text-[var(--color-text-muted)]">·</span>
        <span>LLM: <span className="text-[var(--color-blue)]">{ready.llm_backend}</span></span>
        <span className="text-[var(--color-text-muted)]">·</span>
        <span>Mode: <span className="font-mono">{ready.deployment_mode}</span></span>
        <span className="text-[var(--color-text-muted)]">·</span>
        <span>Status: <span className="text-[var(--color-success)]">{ready.status}</span></span>
      </div>
    </>
  );
}
