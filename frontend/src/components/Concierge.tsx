import { useEffect, useRef, useState } from "react";
import type { Session } from "../types";
import {
  askConcierge,
  fetchChatHistory,
  fetchConciergeOpener,
  fetchNextQuestion,
  type ChatMessage,
  type ConciergeAction,
  type ConciergeCitation,
  type ConciergeContext,
  type ConciergeResponse,
  type SuggestedInput,
} from "../api";
import Button from "./ui/Button";
import SuggestedQuestions from "./chat/SuggestedQuestions";

interface Props {
  /** The case the concierge is currently grounded against. Drives
   * history loading + chat persistence + per-step proactive prompts. */
  caseRecord: Session | null;
  /** What the user is looking at in the center activity panel. Drives
   * retrieval routing — module / sop / queue / case. When omitted, the
   * concierge falls back to a "case" context derived from caseRecord. */
  context?: ConciergeContext;
  /** Short, human label describing the current subject — rendered in
   * a sticky pill at the top of the panel so the user can see exactly
   * what the assistant is grounded against. Helps catch context drift. */
  contextLabel?: string;
  onSuggestionsUpdate?: (suggestions: SuggestedInput[]) => void;
  /** Dispatch a concierge action back into the app. The handler runs
   * the navigation/state change (switch tab, open case, start workflow). */
  onAction?: (action: ConciergeAction) => void;
}

interface Turn {
  role: "user" | "assistant";
  text: string;
  citations: ConciergeCitation[];
  mode: string;
  actions?: ConciergeAction[];
  pending?: boolean;
}

const NO_CASE_OPENER =
  "Hi — I'm your CEN concierge. Ask me anything — I'll pull from your team's FAQ library. " +
  "Open a case anytime and I'll add the workflow context too.";

/**
 * Right-frame AI Concierge — conversational thread persisted to the
 * server. On case open, loads the prior history; every send + reply
 * is appended to chat_messages so the conversation survives refresh.
 *
 * The assistant grounds against three sources (FAQs, current workflow
 * step, prior turns) and surfaces citations with a kind tag so the UI
 * can label them as "FAQ", "Step", etc.
 */
export default function Concierge({
  caseRecord,
  context,
  contextLabel,
  onSuggestionsUpdate,
  onAction,
}: Props) {
  // Effective context — explicit prop wins; otherwise derive from
  // caseRecord (back-compat). Stable across renders for the same case.
  const effectiveContext: ConciergeContext = context ?? {
    kind: caseRecord ? "case" : "none",
    case_id: caseRecord?.id ?? null,
    current_node_id: caseRecord?.pending_node ?? null,
  };
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [opener, setOpener] = useState<string>(NO_CASE_OPENER);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const threadRef = useRef<HTMLDivElement>(null);

  // Load persisted history + opener when the case changes.
  const caseId = caseRecord?.id ?? null;
  useEffect(() => {
    let cancelled = false;
    if (!caseId) {
      setTurns([]);
      setOpener(NO_CASE_OPENER);
      return;
    }
    setHistoryLoading(true);
    setError(null);
    (async () => {
      try {
        const [messages, openerResp] = await Promise.all([
          fetchChatHistory(caseId),
          fetchConciergeOpener(caseId).catch(() => ({ message: "" })),
        ]);
        if (cancelled) return;
        setTurns(
          messages
            .filter((m: ChatMessage) => m.role === "user" || m.role === "assistant")
            .map((m: ChatMessage) => ({
              role: m.role as "user" | "assistant",
              text: m.content,
              citations: m.citations,
              mode: m.mode,
            })),
        );
        if (openerResp.message) setOpener(openerResp.message);
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    })();
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

  // Per-step proactive opener + chip refresh. Fires once per
  // (caseId, pending_node) combo — `seenProactiveForStep` keeps tab
  // switches from re-firing the prompt on the same step.
  const pendingNode = caseRecord?.pending_node ?? null;
  const seenProactiveForStep = useRef<Set<string>>(new Set());
  useEffect(() => {
    let cancelled = false;
    if (!caseId || !pendingNode) {
      setSuggestedQuestions([]);
      return;
    }
    const key = `${caseId}:${pendingNode}`;
    fetchNextQuestion(caseId)
      .then((resp) => {
        if (cancelled) return;
        setSuggestedQuestions(resp.suggested_questions ?? []);
        if (
          resp.prompt &&
          !seenProactiveForStep.current.has(key) &&
          !historyLoading
        ) {
          seenProactiveForStep.current.add(key);
          setTurns((prev) => [
            ...prev,
            {
              role: "assistant",
              text: resp.prompt,
              citations: [],
              mode: "proactive",
            },
          ]);
        }
      })
      .catch(() => {
        if (!cancelled) setSuggestedQuestions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, pendingNode, historyLoading]);

  const sendText = async (rawQuestion: string) => {
    const question = rawQuestion.trim();
    if (!question || busy) return;
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
      const resp: ConciergeResponse = await askConcierge(question, effectiveContext);
      setTurns((prev) => {
        const next = prev.slice(0, -1);
        next.push({
          role: "assistant",
          text: resp.answer,
          citations: resp.citations,
          mode: resp.mode,
          actions: resp.actions,
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

  const send = async () => {
    const q = draft.trim();
    if (!q) return;
    setDraft("");
    await sendText(q);
  };

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex-shrink-0">
        <div className="flex items-center gap-2 px-4 pb-2">
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
        {contextLabel && (
          <div className="mx-4 mb-2 px-2.5 py-1 rounded-md bg-[var(--color-surface-overlay)] border border-[var(--color-border)] text-[10px] text-[var(--color-text-secondary)] flex items-center gap-1.5">
            <span className="text-[var(--color-text-muted)]">Grounded in:</span>
            <span className="font-medium text-[var(--color-text-primary)] truncate">
              {contextLabel}
            </span>
          </div>
        )}
      </div>

      {/* Thread — scrolls inside its bounded region. Header above
          and the input group below are siblings, not children, so the
          form NEVER overlaps the conversation. (Viewport-lock on the
          outer Layout is what guarantees the region is bounded — see
          Layout.tsx h-dvh + min-h-0.) */}
      <div
        ref={threadRef}
        className="flex-1 overflow-y-auto space-y-3 px-4 pb-3 min-h-0"
      >
        {!historyLoading && (
          <div
            className="text-xs leading-relaxed pl-3 border-l-2"
            style={{
              borderColor: "var(--color-blue)",
              color: "var(--color-text-secondary)",
            }}
          >
            {opener}
          </div>
        )}
        {turns.map((t, i) => (
          <ThreadTurn key={i} turn={t} onAction={onAction} />
        ))}
      </div>

      {/* Fixed-region bottom — opaque, no backdrop-blur. Thread ends
          flush against the top of this region; no occlusion. */}
      <div className="flex-shrink-0 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
        {error && (
          <p className="text-[11px] text-[var(--color-danger)] px-4 pt-2">{error}</p>
        )}

        <SuggestedQuestions
          questions={suggestedQuestions}
          onAsk={sendText}
          disabled={busy}
        />

        <form
          className="flex gap-1.5 px-4 pt-1 pb-2"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={
              caseRecord
                ? "Ask about this step…"
                : "Ask anything from your FAQ library…"
            }
            disabled={busy}
            className="flex-1 text-xs"
          />
          <Button
            type="submit"
            disabled={!draft.trim()}
            loading={busy}
            loadingLabel="Thinking…"
          >
            Ask
          </Button>
        </form>

        <p className="text-[10px] text-[var(--color-text-muted)] px-4 pb-3 italic leading-snug">
          I'm a workflow assistant — not a doctor, lawyer, or financial advisor.
          I can't give personalized medical, legal, or financial advice.
        </p>
      </div>
    </div>
  );
}

function ThreadTurn({
  turn,
  onAction,
}: {
  turn: Turn;
  onAction?: (action: ConciergeAction) => void;
}) {
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
      {turn.actions && turn.actions.length > 0 && onAction && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {turn.actions.map((a, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onAction(a)}
              className="text-[11px] px-2.5 py-1 rounded border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white transition-colors font-medium"
            >
              {a.label} →
            </button>
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
      {citation.from_step && (
        <span
          className="inline-block px-1 mr-1 rounded text-[9px] font-medium"
          style={{
            background: "rgba(34,197,94,0.15)",
            border: "1px solid rgb(34,197,94)",
            color: "var(--color-text-secondary)",
          }}
          title="This answer came from a FAQ scoped to the step you're on"
        >
          From this step
        </span>
      )}
      <span className="italic">{citation.question}</span>
    </div>
  );
}
