import type { ReactNode } from "react";
import type { ReadyResponse } from "../types";
import StatusBar from "./StatusBar";

interface Props {
  ready: ReadyResponse | null;
  error: string | null;
  children: ReactNode;
}

export default function Layout({ ready, error, children }: Props) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-[var(--color-border)]">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-[var(--color-text-primary)] flex items-center gap-2.5">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[#4facfe] text-white text-xs font-bold">
                C
              </span>
              CEN AI Concierge
            </h1>
          </div>
          <p className="text-xs text-[var(--color-text-muted)] tracking-wide uppercase">
            Workflow Dashboard
          </p>
        </div>
      </header>
      <StatusBar ready={ready} error={error} />
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
