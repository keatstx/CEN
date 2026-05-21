interface Props {
  side: "left" | "right";
  collapsed: boolean;
  onToggle: () => void;
  className?: string;
}

/**
 * Modern panel-fold collapse icon. NOT a bare `>` chevron — uses an
 * outlined panel-with-fold-mark mark per the FlowUX brief. Rotates
 * depending on side + collapse direction.
 */
export default function CollapseToggle({ side, collapsed, onToggle, className = "" }: Props) {
  const label = collapsed
    ? side === "left"
      ? "Show navigation"
      : "Show assistant"
    : side === "left"
      ? "Hide navigation"
      : "Hide assistant";

  // Direction: the fold mark always points away from the visible panel.
  // Left side: when expanded, fold points LEFT (collapse arrow into the left).
  // When collapsed, fold points RIGHT (expand arrow out to the right).
  // Right side: mirror.
  const pointsLeft =
    (side === "left" && !collapsed) || (side === "right" && collapsed);

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={label}
      className={`inline-flex items-center justify-center w-9 h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-border-hover)] transition-colors ${className}`}
    >
      <svg
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {/* Outer panel rectangle */}
        <rect x="3" y="4" width="18" height="16" rx="2.5" />
        {/* Inner fold line */}
        <line x1="9" y1="4" x2="9" y2="20" />
        {/* Direction indicator inside the smaller pane */}
        {pointsLeft ? (
          <polyline points="6.5,9.5 4.5,12 6.5,14.5" />
        ) : (
          <polyline points="5.5,9.5 7.5,12 5.5,14.5" />
        )}
      </svg>
    </button>
  );
}
