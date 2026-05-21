import { useEffect, useMemo, useState } from "react";
import type { Session, InputField } from "../../types";
import type { SuggestedInput } from "../../api";
import Button from "../ui/Button";
import StepCard from "../StepCard";
import { StepHeader } from "../step_components";

interface Props {
  caseRecord: Session;
  loading: boolean;
  onSubmit: (inputs: Record<string, unknown>) => void;
  onApprove: () => void;
  suggestions: SuggestedInput[];
  onSuggestionApplied?: (key: string) => void;
}

const CONFIDENCE_THRESHOLD = 0.5;

/**
 * Chat-led step renderer. When a case is paused on AWAITING_INPUT and
 * the user is in chat-led mode (default), this component:
 *
 * - Tracks a local `draft` of values the chat has collected so far.
 * - Highlights the *next* unfilled required field with its label +
 *   description and a "type in the chat" affordance.
 * - Watches the `suggestions` prop (fed by the Concierge as the user
 *   replies) for matches at confidence >= 0.5; auto-applies into draft.
 * - Lets the user toggle "Show all fields" to reveal the full StepCard
 *   form hydrated with everything chat has captured.
 * - Submits all collected values in a single `provide_input` call so
 *   the audit chain remains a single mutation per step.
 *
 * For non-AWAITING_INPUT statuses (APPROVAL, COMPLETED, FAILED), this
 * component delegates straight to StepCard — chat-led only applies to
 * input collection.
 */
export default function ChatLedStep(props: Props) {
  if (props.caseRecord.status !== "AWAITING_INPUT") {
    return <StepCard {...props} />;
  }
  // Re-mount on step change so draft resets.
  const stepKey = `${props.caseRecord.pending_node ?? "_"}:awaiting_input`;
  return <ChatLedBody key={stepKey} {...props} />;
}

function ChatLedBody({
  caseRecord,
  loading,
  onSubmit,
  suggestions,
  onSuggestionApplied,
  onApprove,
}: Props) {
  const fields: InputField[] = useMemo(
    () => caseRecord.pending_input_fields ?? [],
    [caseRecord.pending_input_fields],
  );
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [showAll, setShowAll] = useState(false);

  // Auto-apply chat-derived suggestions to the draft when they show up
  // for unfilled required fields at confidence >= threshold. The effect
  // is intentional: incoming suggestions are external data driving local
  // accumulation, and we need the side-effect callback (parent removes
  // the applied suggestion from its list, which is observable state).
  useEffect(() => {
    if (!suggestions.length) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft((prev) => {
      let changed = false;
      const next = { ...prev };
      const fieldByKey = new Map(fields.map((f) => [f.key, f]));
      for (const s of suggestions) {
        const f = fieldByKey.get(s.key);
        if (!f) continue;
        if (next[s.key] !== undefined && next[s.key] !== "") continue;
        if ((s.confidence ?? 0) < CONFIDENCE_THRESHOLD) continue;
        next[s.key] = s.value;
        changed = true;
        onSuggestionApplied?.(s.key);
      }
      return changed ? next : prev;
    });
  }, [suggestions, fields, onSuggestionApplied]);

  // "Show all fields" path: hand off to the full StepCard with
  // everything chat has collected pre-filled.
  if (showAll) {
    return (
      <div className="space-y-3">
        <button
          type="button"
          onClick={() => setShowAll(false)}
          className="text-xs text-[var(--color-accent)] hover:underline"
        >
          ← Back to chat-led mode
        </button>
        <StepCard
          caseRecord={caseRecord}
          loading={loading}
          onSubmit={onSubmit}
          onApprove={onApprove}
          suggestions={suggestions}
          onSuggestionApplied={onSuggestionApplied}
          initialValues={draft}
        />
      </div>
    );
  }

  const requiredFields = fields.filter((f) => f.required);
  const unfilled = requiredFields.filter((f) => {
    const v = draft[f.key];
    return v === undefined || v === null || v === "";
  });
  const allRequiredFilled = unfilled.length === 0;
  const currentField = unfilled[0] ?? null;

  const stepNumber = caseRecord.executed_nodes.length + 1;

  return (
    <div className="card space-y-5">
      <StepHeader
        stepNumber={stepNumber}
        eyebrow="Chat-led step"
        title={currentField?.label || "All set — ready to submit"}
        subtitle={
          currentField
            ? "Answer in the chat on the right. I'll fill this in as you talk."
            : "I've captured everything I need. Review the values below, then submit when ready."
        }
        nodeId={caseRecord.pending_node}
      />

      {currentField && (
        <div className="rounded-lg border border-[var(--color-accent)] bg-[var(--color-accent-glow)] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--color-accent)]">
            Now asking about
          </p>
          <p className="text-base font-medium text-[var(--color-text-primary)] mt-1">
            {currentField.label}
          </p>
          {currentField.description && (
            <p className="text-sm text-[var(--color-text-secondary)] mt-1 leading-relaxed">
              {currentField.description}
            </p>
          )}
        </div>
      )}

      {/* Collected-so-far summary */}
      {Object.keys(draft).length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)]">
            What I've captured
          </p>
          <ul className="space-y-1">
            {fields.map((f) => {
              const v = draft[f.key];
              if (v === undefined || v === null || v === "") return null;
              return (
                <li
                  key={f.key}
                  className="flex items-center justify-between text-sm rounded-md bg-[var(--color-surface-overlay)] px-3 py-2"
                >
                  <span className="text-[var(--color-text-secondary)]">{f.label}</span>
                  <span className="text-[var(--color-text-primary)] font-medium truncate ml-3 max-w-[60%]">
                    {String(v)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="flex items-center gap-3">
        <Button
          size="lg"
          fullWidth
          disabled={!allRequiredFilled}
          loading={loading}
          loadingLabel="Submitting…"
          onClick={() => onSubmit(draft)}
        >
          {allRequiredFilled ? "Submit and continue →" : "Keep going in chat"}
        </Button>
      </div>

      <button
        type="button"
        onClick={() => setShowAll(true)}
        className="w-full text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:underline"
      >
        Show all fields and fill in by hand
      </button>
    </div>
  );
}
