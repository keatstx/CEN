interface Props {
  questions: string[];
  onAsk: (question: string) => void;
  disabled?: boolean;
}

/**
 * Step-aware chip panel rendered above the Concierge input. Each chip
 * is one of the AOP node's hand-authored `suggested_questions`. Click
 * = send as a user message via the parent's `onAsk` callback.
 *
 * Returns null when there are no questions so the panel disappears
 * cleanly rather than showing an empty container.
 */
export default function SuggestedQuestions({ questions, onAsk, disabled }: Props) {
  if (!questions.length) return null;
  return (
    <div className="px-4 pb-2">
      <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
        Ask me about this step
      </p>
      <div className="flex flex-wrap gap-1.5">
        {questions.map((q, i) => (
          <button
            key={i}
            type="button"
            onClick={() => onAsk(q)}
            disabled={disabled}
            className="text-xs px-2.5 py-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-glow)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Ask the assistant this question"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
