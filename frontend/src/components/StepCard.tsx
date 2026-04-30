import { useState } from "react";
import type { Session } from "../types";
import { type SuggestedInput } from "../api";
import Button from "./ui/Button";
import SuggestionsPanel from "./SuggestionsPanel";
import { FieldInput, StepHeader } from "./step_components";

interface Props {
  caseRecord: Session;
  loading: boolean;
  onSubmit: (inputs: Record<string, unknown>) => void;
  onApprove: () => void;
  suggestions?: SuggestedInput[];
  onSuggestionApplied?: (key: string) => void;
}

/**
 * StepCard renders the *current* step of a case in the middle frame
 * with a real handhold UX — large step number, friendly headline,
 * descriptive subtext, contextual summary panel, and clear next action.
 *
 * - AWAITING_INPUT: form derived from pending_input_fields with field
 *   descriptions, friendly placeholders, and a primary CTA labelled
 *   for the action ("Submit and continue").
 * - AWAITING_APPROVAL: shows what's been collected so far in a summary
 *   card so the approval is informed, not blind.
 * - COMPLETED: success card with totals and outcome.
 * - FAILED: plain-language error card with a recovery hint.
 *
 * Concierge suggestions: when the user has stated values mid-chat,
 * the right panel extracts them and the parent passes them in via
 * `suggestions`. We render a compact "Apply" panel above the form so
 * one tap fills the field. The user still presses Submit — this keeps
 * the audit chain unbroken (provide_input is the only write path).
 */
export default function StepCard(props: Props) {
  // Reset form state when the step changes by remounting via key.
  const stepKey = `${props.caseRecord.pending_node ?? "_"}:${props.caseRecord.status}`;
  return <StepCardBody key={stepKey} {...props} />;
}

function StepCardBody({
  caseRecord,
  loading,
  onSubmit,
  onApprove,
  suggestions = [],
  onSuggestionApplied,
}: Props) {
  const [values, setValues] = useState<Record<string, unknown>>({});

  const stepNumber = caseRecord.executed_nodes.length + 1;

  // ─────────────── COMPLETED ───────────────
  if (caseRecord.status === "COMPLETED") {
    return (
      <div className="card space-y-4">
        <div className="flex items-start gap-3">
          <div
            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white text-lg font-bold"
            style={{ background: "var(--color-success)" }}
          >
            ✓
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
              All steps complete
            </p>
            <h3 className="text-lg font-semibold mt-0.5">
              You're done with this case
            </h3>
          </div>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
          The workflow finished successfully. {caseRecord.executed_nodes.length}{" "}
          step{caseRecord.executed_nodes.length === 1 ? "" : "s"} ran from start
          to finish. You can review everything that was collected in the
          "Information so far" panel above, or start a new case for the same
          patient from the left panel.
        </p>
      </div>
    );
  }

  // ─────────────── FAILED ───────────────
  if (caseRecord.status === "FAILED") {
    return (
      <div
        className="card space-y-4 border-l-4"
        style={{ borderLeftColor: "var(--color-danger)" }}
      >
        <div className="flex items-start gap-3">
          <div
            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white text-lg font-bold"
            style={{ background: "var(--color-danger)" }}
          >
            !
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
              Workflow stopped
            </p>
            <h3 className="text-lg font-semibold mt-0.5">
              Something went wrong
            </h3>
          </div>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
          The workflow stopped before it could finish. Start a new case from
          the left panel to try again, or ask the AI Concierge on the right if
          you're not sure what happened.
        </p>
      </div>
    );
  }

  // ─────────────── AWAITING_APPROVAL ───────────────
  if (caseRecord.status === "AWAITING_APPROVAL") {
    return (
      <div className="card space-y-5">
        <StepHeader
          stepNumber={stepNumber}
          eyebrow="Your turn"
          title="Review and approve"
          subtitle="The workflow needs your sign-off before it can continue. Review the Information so far panel above to confirm what was captured, then approve to move on."
          nodeId={caseRecord.pending_node}
        />

        <Button
          size="lg"
          fullWidth
          loading={loading}
          loadingLabel="Submitting your approval…"
          onClick={onApprove}
        >
          Looks good — approve and continue →
        </Button>
      </div>
    );
  }

  // ─────────────── AWAITING_INPUT ───────────────
  if (caseRecord.status === "AWAITING_INPUT") {
    const fields = caseRecord.pending_input_fields ?? [];
    const allRequiredFilled = fields
      .filter((f) => f.required)
      .every((f) => {
        const v = values[f.key];
        return v !== undefined && v !== null && v !== "";
      });

    const stepTitle = fields[0]?.label || "We need a bit more information";
    const stepSubtitle = fields[0]?.description
      ? "Fill in the details below to continue."
      : "Take a moment to provide the information below — it'll be used in later steps.";

    // Only show suggestions whose key matches a currently-pending field
    // and whose value isn't already filled in the form (avoid noise).
    const fieldKeys = new Set(fields.map((f) => f.key));
    const visibleSuggestions = suggestions.filter(
      (s) =>
        fieldKeys.has(s.key) &&
        (values[s.key] === undefined || values[s.key] === ""),
    );

    const applySuggestion = (s: SuggestedInput) => {
      setValues((prev) => ({ ...prev, [s.key]: s.value }));
      onSuggestionApplied?.(s.key);
    };

    return (
      <div className="card space-y-5">
        <StepHeader
          stepNumber={stepNumber}
          eyebrow="Your turn"
          title={stepTitle}
          subtitle={stepSubtitle}
          nodeId={caseRecord.pending_node}
        />

        {visibleSuggestions.length > 0 && (
          <SuggestionsPanel
            suggestions={visibleSuggestions}
            fields={fields}
            onApply={applySuggestion}
          />
        )}

        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (allRequiredFilled && !loading) onSubmit(values);
          }}
        >
          {fields.map((field, idx) => (
            <FieldInput
              key={field.key}
              field={field}
              isFirst={idx === 0}
              value={values[field.key]}
              caseId={caseRecord.id}
              nodeId={caseRecord.pending_node ?? undefined}
              onChange={(v) =>
                setValues((prev) => ({ ...prev, [field.key]: v }))
              }
            />
          ))}
          <Button
            type="submit"
            size="lg"
            fullWidth
            disabled={!allRequiredFilled}
            loading={loading}
            loadingLabel="Submitting…"
            className="mt-2"
          >
            Submit and continue →
          </Button>
          {!allRequiredFilled && (
            <p className="text-[11px] text-[var(--color-text-muted)] text-center">
              Fill in the required fields to continue.
            </p>
          )}
        </form>
      </div>
    );
  }

  // ─────────────── ACTIVE (transient) ───────────────
  return (
    <div className="card flex items-center justify-center min-h-[200px]">
      <div className="text-center space-y-2">
        <div className="inline-block w-6 h-6 border-2 border-[var(--color-text-muted)] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[var(--color-text-muted)]">
          Working on the next step…
        </p>
      </div>
    </div>
  );
}

