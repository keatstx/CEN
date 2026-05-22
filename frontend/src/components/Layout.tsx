import type { ReactNode } from "react";
import type { ReadyResponse } from "../types";
import StatusBar from "./StatusBar";
import CollapseToggle from "./CollapseToggle";

interface Props {
  ready: ReadyResponse | null;
  error: string | null;
  /** Left rail content — typically the LeftNav (owns its own collapse toggle). */
  leftRail: ReactNode;
  /** Center "Studio" — the active tab's content. */
  children: ReactNode;
  /** Right rail content — typically the Concierge. */
  rightRail: ReactNode;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  onToggleRight: () => void;
}

const COLLAPSED_RAIL_WIDTH = "56px";

export default function Layout({
  ready,
  error,
  leftRail,
  children,
  rightRail,
  leftCollapsed,
  rightCollapsed,
  onToggleRight,
}: Props) {
  const leftWidth = leftCollapsed ? COLLAPSED_RAIL_WIDTH : "var(--left-rail-width)";
  const rightWidth = rightCollapsed ? COLLAPSED_RAIL_WIDTH : "var(--right-rail-width)";

  return (
    // Viewport-locked outer: the page itself never scrolls. Each grid
    // column scrolls internally instead — same pattern as Slack/Linear/
    // VSCode. This is what guarantees the right-rail's sticky form
    // sits at the bottom of the visible viewport regardless of how
    // tall the center content gets. `h-dvh` (dynamic viewport height)
    // beats `h-screen` on mobile where the browser chrome shifts.
    <div className="h-dvh flex flex-col overflow-hidden">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)] flex-shrink-0">
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ConcitorMark />
            <div className="leading-tight">
              <h1 className="text-base font-semibold tracking-tight text-[var(--color-text-primary)]">
                Concitor
              </h1>
              <p className="text-[11px] text-[var(--color-text-muted)] tracking-wide uppercase">
                CEN · Community Equity Navigators
              </p>
            </div>
          </div>
          <p className="text-xs text-[var(--color-text-muted)] tracking-wide uppercase">
            FlowUX Studio
          </p>
        </div>
      </header>

      <div className="flex-shrink-0">
        <StatusBar ready={ready} error={error} />
      </div>

      {/* `min-h-0` lets the grid row shrink-fit instead of growing to
          its content (the default for flex children — without this,
          internal overflow doesn't trigger). */}
      <div
        className="flex-1 min-h-0 grid"
        style={{
          gridTemplateColumns: `${leftWidth} 1fr ${rightWidth}`,
          transition: "grid-template-columns 0.2s ease",
        }}
      >
        <aside
          className="border-r border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden min-h-0"
          aria-label="Primary navigation"
        >
          {leftRail}
        </aside>

        <main className="overflow-y-auto bg-[var(--color-surface)] px-6 py-6 min-w-0 min-h-0">
          {children}
        </main>

        <aside
          className="border-l border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden flex flex-col min-h-0"
          aria-label="AI assistant"
        >
          {rightCollapsed ? (
            <div className="flex items-center justify-center px-3 pt-3 pb-2">
              <CollapseToggle side="right" collapsed onToggle={onToggleRight} />
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between px-4 pt-3 pb-2 flex-shrink-0">
                <p className="text-xs text-[var(--color-text-muted)] tracking-wide uppercase">
                  Assistant
                </p>
                <CollapseToggle side="right" collapsed={false} onToggle={onToggleRight} />
              </div>
              <div className="flex-1 min-h-0 overflow-hidden">{rightRail}</div>
            </>
          )}
        </aside>
      </div>

      <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-2 flex items-center justify-between text-xs text-[var(--color-text-muted)] flex-shrink-0">
        <span>
          Powered by{" "}
          <a
            href="https://concitor.com"
            target="_blank"
            rel="noreferrer"
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] transition-colors font-medium"
          >
            Concitor
          </a>
        </span>
        <span className="hidden sm:inline">
          Workflows are data · Audit trail is the backbone · Plain language always
        </span>
      </footer>
    </div>
  );
}

function ConcitorMark() {
  // Wordmark surrogate — outlined block-C in orange + black. When the
  // real Concitor lockup is provided, swap this SVG out.
  return (
    <span
      className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-[var(--color-primary)]"
      aria-hidden
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--color-accent)" strokeWidth="2.5" strokeLinecap="round">
        <path d="M17 7a7 7 0 1 0 0 10" />
      </svg>
    </span>
  );
}
