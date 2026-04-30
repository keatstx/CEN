import type { ButtonHTMLAttributes, ReactNode } from "react";
import Spinner from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Show a spinner + disable + replace the label with `loadingLabel`
   * (or keep the children if no loading label is supplied). Use this
   * for any button that triggers an async action. */
  loading?: boolean;
  /** Optional copy shown while loading. Falls back to children if
   * unset. Examples: "Uploading…", "Saving…". */
  loadingLabel?: ReactNode;
  variant?: Variant;
  size?: Size;
  /** Pulls the button to the full width of its container. */
  fullWidth?: boolean;
}

/**
 * Universal action button.
 *
 * Every button that triggers a network round-trip should use this with
 * `loading={busy}` and (optionally) `loadingLabel`. It guarantees:
 *
 * - A consistent spinner appears next to the label (no more silent
 *   "is anything happening?" moments).
 * - The button auto-disables while loading (no double-fire).
 * - Variants stay consistent across the tool.
 *
 * For file-input triggers, prefer wrapping in a `<label htmlFor=…>`
 * with the actual `<input type="file">` hidden; this Button doesn't
 * try to do file-input duty itself.
 */
export default function Button({
  loading = false,
  loadingLabel,
  variant = "primary",
  size = "md",
  fullWidth = false,
  disabled,
  className,
  children,
  ...rest
}: Props) {
  const isDisabled = disabled || loading;
  const palette = _palette(variant);
  const sizing = _sizing(size);

  return (
    <button
      {...rest}
      disabled={isDisabled}
      className={[
        "inline-flex items-center justify-center gap-1.5 rounded font-medium",
        "transition-colors border",
        sizing,
        fullWidth ? "w-full" : "",
        isDisabled ? "opacity-60 cursor-not-allowed" : "cursor-pointer",
        className ?? "",
      ].join(" ")}
      style={{
        background: palette.bg,
        color: palette.fg,
        borderColor: palette.border,
      }}
    >
      {loading && <Spinner size={size === "lg" ? 16 : 13} />}
      <span>{loading ? (loadingLabel ?? children) : children}</span>
    </button>
  );
}

// ── Style maps ──────────────────────────────────────────────────────


function _sizing(size: Size): string {
  switch (size) {
    case "sm":
      return "text-[11px] px-2 py-1";
    case "lg":
      return "text-sm px-4 py-2.5";
    default:
      return "text-xs px-3 py-1.5";
  }
}

function _palette(variant: Variant): {
  bg: string;
  fg: string;
  border: string;
} {
  switch (variant) {
    case "primary":
      return {
        bg: "var(--color-accent)",
        fg: "white",
        border: "var(--color-accent)",
      };
    case "secondary":
      return {
        bg: "var(--color-bg)",
        fg: "var(--color-text-primary)",
        border: "var(--color-border)",
      };
    case "ghost":
      return {
        bg: "transparent",
        fg: "var(--color-accent)",
        border:
          "color-mix(in srgb, var(--color-accent) 30%, transparent)",
      };
    case "danger":
      return {
        bg: "var(--color-danger)",
        fg: "white",
        border: "var(--color-danger)",
      };
  }
}
