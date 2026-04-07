import { useState } from "react";
import type { Session } from "../types";
import { askConcierge, type ConciergeResponse } from "../api";

interface Props {
  caseRecord: Session | null;
}

interface Turn {
  role: "user" | "assistant";
  text: string;
  citations?: { question: string; score: number }[];
  mode?: string;
}

/**
 * Right-frame AI Concierge. Calls /concierge/ask which retrieves
 * matching FAQs from the project's knowledge base and returns the
 * top match (lookup mode) or a formatted synthesis (format mode —
 * lands when Gemini is wired in a follow-up).
 *
 * Conversation history is component-state-only in v1 (lost on refresh).
 * Per-turn persistence to a chat_messages table is a v2 item.
 */
export default function Concierge({ caseRecord }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    const question = draft.trim();
    if (!question || busy) return;
    setDraft("");
    setError(null);
    setTurns((prev) => [...prev, { role: "user", text: question }]);
    setBusy(true);
    try {
      const resp: ConciergeResponse = await askConcierge(
        question,
        caseRecord?.id,
      );
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          text: resp.answer,
          citations: resp.citations.map((c) => ({
            question: c.question,
            score: c.score,
          })),
          mode: resp.mode,
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Concierge unavailable");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card flex flex-col sticky top-6 max-h-[calc(100vh-4rem)]">
      <div className="flex items-center gap-2 mb-3">
        <span
          className="inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: "var(--color-blue)" }}
        />
        <h3 className="text-sm font-semibold">AI Concierge</h3>
      </div>

      {/* Thread */}
      <div className="flex-1 overflow-y-auto space-y-3 -mx-1 px-1 mb-3 min-h-[200px]">
        {turns.length === 0 && (
          <p className="text-xs text-[var(--color-text-muted)] italic">
            Ask any question about this step in plain language. I'll answer
            using the FAQs your team has uploaded for this project.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i}>
            {t.role === "user" ? (
              <div className="flex justify-end">
                <div className="max-w-[90%] bg-[var(--color-bg)] border border-[var(--color-border)] px-3 py-2 rounded-lg text-xs">
                  {t.text}
                </div>
              </div>
            ) : (
              <div className="max-w-[95%]">
                <div className="text-xs whitespace-pre-wrap leading-relaxed text-[var(--color-text-secondary)]">
                  {t.text}
                </div>
                {t.citations && t.citations.length > 0 && (
                  <div className="mt-1.5 space-y-0.5">
                    {t.citations.map((c, idx) => (
                      <div
                        key={idx}
                        className="text-[10px] text-[var(--color-text-muted)] truncate"
                      >
                        ↳ <span className="italic">{c.question}</span>
                      </div>
                    ))}
                  </div>
                )}
                {t.mode === "guardrail" && (
                  <div className="mt-1 text-[10px] text-[var(--color-warning)]">
                    Out-of-scope question — referred elsewhere
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="text-xs text-[var(--color-text-muted)] italic">
            Looking…
          </div>
        )}
      </div>

      {error && (
        <p className="text-[11px] text-[var(--color-danger)] mb-2">{error}</p>
      )}

      <form
        className="flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about this step…"
          disabled={busy}
          className="flex-1 text-xs"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="btn btn-primary text-xs px-3"
        >
          Ask
        </button>
      </form>

      <p className="text-[10px] text-[var(--color-text-muted)] mt-2 italic leading-snug">
        I'm a workflow assistant — not a doctor, lawyer, or financial advisor.
        I can't give personalized medical, legal, or financial advice.
      </p>
    </div>
  );
}
