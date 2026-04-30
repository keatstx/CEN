/**
 * Human-friendly relative-time formatter.
 *
 * "just now" / "2m ago" / "3h ago" / "5d ago". Returns the original
 * string when the input can't be parsed, and an empty string when the
 * input is empty. Used across the case sidebar, dashboard cards, and
 * anywhere a timestamp is rendered to a navigator.
 */
export function relativeTime(iso: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}

/**
 * Days-until-due formatter. Returns "Overdue" for past dates,
 * "Due today", "Due tomorrow", "Due in 3 days", etc.
 */
export function dueLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) return "";
  const diffMs = target - Date.now();
  const diffDays = Math.round(diffMs / 86400000);
  if (diffDays < 0) return "Overdue";
  if (diffDays === 0) return "Due today";
  if (diffDays === 1) return "Due tomorrow";
  return `Due in ${diffDays} days`;
}
