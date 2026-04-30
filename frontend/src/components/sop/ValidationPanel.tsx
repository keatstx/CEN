import { useEffect, useRef, useState } from "react";
import {
  applySOPFix,
  autoFixSOP,
  type DraftEditResponse,
} from "../../api";
import type { ProposedFix, SOPRecord, ValidationIssue } from "../../types";
import Spinner from "../ui/Spinner";

interface Props {
  sop: SOPRecord;
  /** Called after every successful fix application — parent re-fetches
   * the SOP record so the table + issue list re-render. */
  onDraftUpdated: (updated: DraftEditResponse) => void;
  /** When set (typically because the user clicked a node on the DAG),
   * the panel scrolls the first matching issue into view and bolds
   * its border. */
  highlightNodeId?: string | null;
}

/**
 * Interactive validation panel: every issue carries 1-3 fix proposals
 * the navigator can apply with one tap. Errors first, warnings below.
 * "Auto-fix what you can" applies every confidence-≥-0.9 fix in a
 * batch.
 *
 * The fix engine + apply path lives in the backend
 * (`src/cen/sop/fixer.py` + `/api/sop/{id}/apply_fix`). This component
 * is only the UI — every change goes through the server so the
 * validator + audit chain stay authoritative.
 */
export default function ValidationPanel({
  sop,
  onDraftUpdated,
  highlightNodeId,
}: Props) {
  const highlightRef = useRef<HTMLLIElement | null>(null);

  // When the DAG node selection changes, scroll the matching issue
  // into view (the first one — issues for the same node group
  // visually).
  useEffect(() => {
    if (highlightNodeId && highlightRef.current) {
      highlightRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [highlightNodeId]);

  // Track which specific action is in flight so the spinner appears on
  // the right button (not the whole panel) — the user knows exactly
  // what's processing.
  const [appliedFixKey, setAppliedFixKey] = useState<string | null>(null);
  const [autoFixing, setAutoFixing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = appliedFixKey !== null || autoFixing;

  const errors = sop.validation_issues.filter((i) => i.severity === "error");
  const warnings = sop.validation_issues.filter((i) => i.severity === "warning");
  const hasAnyHighConfidence = sop.validation_issues.some((i) =>
    i.fixes.some((f) => f.confidence >= 0.9),
  );

  const apply = async (fix: ProposedFix, key: string) => {
    setAppliedFixKey(key);
    setError(null);
    try {
      const result = await applySOPFix(sop.id, fix);
      onDraftUpdated(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAppliedFixKey(null);
    }
  };

  const autoFix = async () => {
    setAutoFixing(true);
    setError(null);
    try {
      const result = await autoFixSOP(sop.id);
      onDraftUpdated(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAutoFixing(false);
    }
  };

  if (errors.length === 0 && warnings.length === 0) {
    return (
      <div className="card" style={{ borderColor: "var(--color-success)" }}>
        <p className="text-sm">✓ The draft looks clean — no issues found.</p>
      </div>
    );
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          Review notes
          <span className="ml-2 text-xs text-[var(--color-text-muted)] font-normal">
            {errors.length} {errors.length === 1 ? "issue" : "issues"} to fix,{" "}
            {warnings.length}{" "}
            {warnings.length === 1 ? "warning" : "warnings"}
          </span>
        </h3>
        {hasAnyHighConfidence && (
          <button
            type="button"
            onClick={autoFix}
            disabled={busy}
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded border hover:bg-[var(--color-bg)] disabled:opacity-60"
            style={{
              color: "var(--color-accent)",
              borderColor:
                "color-mix(in srgb, var(--color-accent) 30%, transparent)",
            }}
            title="Apply every fix with high confidence in one batch"
          >
            {autoFixing && <Spinner size={11} />}
            {autoFixing ? "Auto-fixing…" : "Auto-fix what I can"}
          </button>
        )}
      </div>

      {error && (
        <p
          className="text-[11px]"
          style={{ color: "var(--color-error)" }}
        >
          {error}
        </p>
      )}

      <ul className="space-y-2">
        {errors.map((issue, idx) => {
          const isHighlight =
            !!highlightNodeId && issue.node_id === highlightNodeId;
          return (
            <IssueRow
              key={`e-${idx}`}
              issueKey={`e-${idx}`}
              issue={issue}
              severity="error"
              onApply={apply}
              busy={busy}
              appliedFixKey={appliedFixKey}
              highlight={isHighlight}
              rowRef={isHighlight ? highlightRef : undefined}
            />
          );
        })}
        {warnings.map((issue, idx) => {
          const isHighlight =
            !!highlightNodeId && issue.node_id === highlightNodeId;
          return (
            <IssueRow
              key={`w-${idx}`}
              issueKey={`w-${idx}`}
              issue={issue}
              severity="warning"
              onApply={apply}
              busy={busy}
              appliedFixKey={appliedFixKey}
              highlight={isHighlight}
              rowRef={isHighlight ? highlightRef : undefined}
            />
          );
        })}
      </ul>
    </div>
  );
}

function IssueRow({
  issue,
  issueKey,
  severity,
  onApply,
  busy,
  appliedFixKey,
  highlight,
  rowRef,
}: {
  issue: ValidationIssue;
  issueKey: string;
  severity: "error" | "warning";
  onApply: (fix: ProposedFix, key: string) => void;
  busy: boolean;
  appliedFixKey: string | null;
  highlight: boolean;
  rowRef?: React.Ref<HTMLLIElement>;
}) {
  const color =
    severity === "error" ? "var(--color-error)" : "var(--color-warning, #b45309)";
  return (
    <li
      ref={rowRef}
      className={`text-xs space-y-1.5 pl-2 border-l-2 transition-all ${
        highlight ? "bg-[var(--color-bg)] -mx-3 px-3 py-2 rounded" : ""
      }`}
      style={{
        borderColor: color,
        borderLeftWidth: highlight ? "4px" : "2px",
      }}
    >
      <div style={{ color }}>
        {issue.node_id ? <code className="font-mono mr-1">{issue.node_id}</code> : null}
        {issue.message}
      </div>
      {issue.fixes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {issue.fixes.map((fix, i) => {
            const fixKey = `${issueKey}-${i}`;
            const thisLoading = appliedFixKey === fixKey;
            return (
              <button
                key={i}
                type="button"
                disabled={busy}
                onClick={() => onApply(fix, fixKey)}
                className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded border hover:bg-[var(--color-bg)] transition-colors disabled:opacity-60"
                style={{
                  color: "var(--color-accent)",
                  borderColor:
                    "color-mix(in srgb, var(--color-accent) 30%, transparent)",
                }}
                title={`${fix.label} (confidence ${Math.round(fix.confidence * 100)}%)`}
              >
                {thisLoading && <Spinner size={11} />}
                {thisLoading ? "Applying…" : fix.label}
              </button>
            );
          })}
        </div>
      )}
    </li>
  );
}
