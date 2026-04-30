import type { Session } from "../types";

/**
 * Single source of truth for case status labels and colors.
 *
 * Imported by CaseSidebar, Dashboard, Stepper, and any other component
 * that displays case status. Per CLAUDE.md §5 the labels are plain
 * navigator language — never raw enum values.
 */
export const STATUS_LABEL: Record<Session["status"], string> = {
  ACTIVE: "In progress",
  AWAITING_INPUT: "Needs your input",
  AWAITING_APPROVAL: "Awaiting review",
  AWAITING_EXTERNAL: "Sent to specialist",
  COMPLETED: "Done",
  FAILED: "Stopped",
};

export const STATUS_COLOR: Record<Session["status"], string> = {
  ACTIVE: "var(--color-blue)",
  AWAITING_INPUT: "var(--color-warning)",
  AWAITING_APPROVAL: "var(--color-warning)",
  AWAITING_EXTERNAL: "var(--color-blue)",
  COMPLETED: "var(--color-success)",
  FAILED: "var(--color-danger)",
};
