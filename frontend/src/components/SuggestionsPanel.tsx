import type { InputField } from "../types";
import type { SuggestedInput } from "../api";

interface Props {
  suggestions: SuggestedInput[];
  fields: InputField[];
  onApply: (s: SuggestedInput) => void;
}

/**
 * Compact "from the chat" panel that surfaces structured values the
 * concierge extracted from the conversation. The navigator taps Apply
 * to fill the field below — they still hit Submit themselves so the
 * existing provide_input audit trail stays unbroken.
 */
export default function SuggestionsPanel({
  suggestions,
  fields,
  onApply,
}: Props) {
  if (suggestions.length === 0) return null;

  return (
    <div
      className="rounded-md border px-3 py-2.5 space-y-2"
      style={{
        background: "color-mix(in srgb, var(--color-blue) 6%, transparent)",
        borderColor: "color-mix(in srgb, var(--color-blue) 25%, transparent)",
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-block w-2 h-2 rounded-full"
          style={{ background: "var(--color-blue)" }}
        />
        <p className="text-[11px] font-semibold tracking-wide uppercase text-[var(--color-text-muted)]">
          From your chat — apply to fill these in?
        </p>
      </div>
      <ul className="space-y-1.5">
        {suggestions.map((s) => (
          <SuggestionRow
            key={s.key}
            suggestion={s}
            field={fields.find((f) => f.key === s.key)}
            onApply={() => onApply(s)}
          />
        ))}
      </ul>
    </div>
  );
}

function SuggestionRow({
  suggestion,
  field,
  onApply,
}: {
  suggestion: SuggestedInput;
  field: InputField | undefined;
  onApply: () => void;
}) {
  const label = field?.label || suggestion.key;
  const display = formatValue(suggestion.value, field?.type);
  const tier = confidenceTier(suggestion.confidence);

  return (
    <li className="flex items-start justify-between gap-2 text-xs">
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className="font-medium text-[var(--color-text-primary)]">
            {label}:
          </span>
          <span className="font-mono text-[var(--color-text-secondary)]">
            {display}
          </span>
          <ConfidenceBadge tier={tier} />
        </div>
        {suggestion.evidence && (
          <p className="text-[10px] text-[var(--color-text-muted)] italic truncate mt-0.5">
            From: "{suggestion.evidence}"
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={onApply}
        className="text-[11px] font-medium px-2 py-1 rounded border hover:bg-[var(--color-bg)] transition-colors flex-shrink-0"
        style={{
          color: "var(--color-blue)",
          borderColor: "color-mix(in srgb, var(--color-blue) 30%, transparent)",
        }}
      >
        Apply
      </button>
    </li>
  );
}

function ConfidenceBadge({ tier }: { tier: "high" | "medium" | "low" }) {
  const palette = {
    high: { bg: "var(--color-success)", label: "high confidence" },
    medium: { bg: "var(--color-warning, #b45309)", label: "medium confidence" },
    low: { bg: "var(--color-text-muted)", label: "low confidence" },
  };
  const { bg, label } = palette[tier];
  return (
    <span
      className="text-[9px] uppercase tracking-wider px-1 rounded"
      style={{
        background: `color-mix(in srgb, ${bg} 18%, transparent)`,
        color: bg,
      }}
      title={label}
    >
      {tier}
    </span>
  );
}

function confidenceTier(c: number): "high" | "medium" | "low" {
  if (c >= 0.8) return "high";
  if (c >= 0.6) return "medium";
  return "low";
}

function formatValue(value: unknown, fieldType: string | undefined): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (fieldType === "currency") {
      return value.toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      });
    }
    return value.toLocaleString("en-US");
  }
  return String(value);
}
