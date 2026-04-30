interface Props {
  /** px size; defaults to 14 (matches text-xs button content). */
  size?: number;
  /** Optional explicit color; defaults to currentColor so it inherits
   * from the surrounding text. */
  color?: string;
  className?: string;
}

/**
 * Small inline spinner — a 360°-rotating SVG ring.
 *
 * Used by `<Button loading>` and anywhere a status swirl needs to
 * appear next to text. The animation is the Tailwind built-in
 * `animate-spin`, which is part of the v3 base preset.
 */
export default function Spinner({ size = 14, color, className }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`animate-spin ${className ?? ""}`}
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke={color ?? "currentColor"}
        strokeOpacity="0.25"
        strokeWidth="3"
      />
      <path
        d="M 12 2 A 10 10 0 0 1 22 12"
        stroke={color ?? "currentColor"}
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
