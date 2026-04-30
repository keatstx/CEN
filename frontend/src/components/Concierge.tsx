import { useEffect, useRef, useState } from "react";
import type { Session } from "../types";
import {
  askConcierge,
  fetchChatHistory,
  type ChatMessage,
  type ConciergeCitation,
  type ConciergeResponse,
  type SuggestedInput,
} from "../api";

interface Props {
  caseRecord: Session | null;
  onSuggestionsUpdate?: (suggestions: SuggestedInput[]) => void;
}

interface Turn {
  role: "user" | "assistant";
  text: string;
  citations: ConciergeCitation[];
  mode: string;
  pending?: boolean;
}

/**
 * Right-frame AI Concierge — conversational thread persisted to the
 * server. On case open, loads the prior history; every send + reply
 * is appended to chat_messages so the conversation survives refresh.
 *
 * The assistant grounds against three sources (FAQs, current workflow
 * step, prior turns) and surfaces citations with a kind tag so the UI
 * can label them as "FAQ", "Step", etc.
 */
export default function Concierge({ caseRecord, onSuggestionsUpdate }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  // Load persisted history when the case changes.
  const caseId = caseRecord?.id ?? null;
  useEffect(() => {
    let cancelled = false;
    if (!caseId) {
      setTurns([]);
      return;
    }
    setHistoryLoading(true);
    setError(null);
    fetchChatHistory(caseId)
      .then((messages: ChatMessage[]) => {
        if (cancelled) return;
        setTurns(
          messages
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((m) => ({
              role: m.role as "user" | "assistant",
              text: m.content,
              citations: m.citations,
              mode: m.mode,
            })),
        );
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  // Auto-scroll to bottom on new turn.
  useEffect(() => {
    threadRef.current?.scrollTo({
      top: threadRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns.length]);

  const send = async () => {
    const question = draft.trim();
    if (!question || busy) return;
    setDraft("");
    setError(null);
    // Optimistic append; the server will persist both user + assistant.
    setTurns((prev) => [
      ...prev,
      { role: "user", text: question, citations: [], mode: "" },
      {
        role: "assistant",
        text: "Thinking…",
        citations: [],
        mode: "",
        pending: true,
      },
    ]);
    setBusy(true);
    try {
      const resp: ConciergeResponse = await askConcierge(
        question,
        caseRecord?.id,
        caseRecord?.pending_node ?? undefined,
      );
      setTurns((prev) => {
        const next = prev.slice(0, -1);
        next.push({
          role: "assistant",
          text: resp.answer,
          citations: resp.citations,
          mode: resp.mode,
        });
        return next;
      });
      // Bubble freshly-extracted suggestions up to the parent so the
      // StepCard can render them above the form.
      if (resp.suggested_inputs && onSuggestionsUpdate) {
        onSuggestionsUpdate(resp.suggested_inputs);
      }
    } catch (e) {
      // Drop the pending placeholder on error.
      setTurns((prev) => prev.slice(0, -1));
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
        {historyLoading && (
          <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">
            Loading thread…
          </span>
        )}
      </div>

      {/* Thread */}
      <div
        ref={threadRef}
        className="flex-1 overflow-y-auto space-y-3 -mx-1 px-1 mb-3 min-h-[200px]"
      >
        {turns.length === 0 && !historyLoading && (
          <p className="text-xs text-[var(--color-text-muted)] italic">
            {caseRecord
              ? "Hi — ask me anything about this case. I'll pull from your team's FAQs and the current step."
              : "Open a case and I'll be here to help walk through it."}
          </p>
        )}
        {turns.map((t, i) => (
          <ThreadTurn key={i} turn={t} />
        ))}
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
          placeholder={caseRecord ? "Ask about this step…" : "Open a case to chat"}
          disabled={busy || !caseRecord}
          className="flex-1 text-xs"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim() || !caseRecord}
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

function ThreadTurn({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[90%] bg-[var(--color-bg)] border border-[var(--color-border)] px-3 py-2 rounded-lg text-xs">
          {turn.text}
        </div>
      </div>
    );
  }
  return (
    <div className="max-w-[95%]">
      <div
        className={`text-xs whitespace-pre-wrap leading-relaxed ${
          turn.pending
            ? "italic text-[var(--color-text-muted)]"
            : "text-[var(--color-text-secondary)]"
        }`}
      >
        {turn.text}
      </div>
      {turn.citations && turn.citations.length > 0 && (
        <div className="mt-1.5 space-y-0.5">
          {turn.citations.map((c, idx) => (
            <CitationLine key={idx} citation={c} />
          ))}
        </div>
      )}
      {turn.mode === "guardrail" && (
        <div className="mt-1 text-[10px] text-[var(--color-warning)]">
          Out-of-scope question — referred elsewhere
        </div>
      )}
      {turn.mode === "no_match" && (
        <div className="mt-1 text-[10px] text-[var(--color-text-muted)]">
          Tip: your team can add this Q to the FAQ library.
        </div>
      )}
    </div>
  );
}

function CitationLine({ citation }: { citation: ConciergeCitation }) {
  const tag =
    citation.kind === "workflow"
      ? "Step"
      : citation.kind === "sop"
      ? "SOP"
      : citation.kind === "case_context"
      ? "Case"
      : "FAQ";
  return (
    <div className="text-[10px] text-[var(--color-text-muted)] truncate">
      <span
        className="inline-block px-1 mr-1 rounded text-[9px] font-mono"
        style={{
          background: "var(--color-bg)",
          border: "1px solid var(--color-border)",
        }}
      >
        {tag}
      </span>
      <span className="italic">{citation.question}</span>
    </div>
  );
}
