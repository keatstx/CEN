import { useState } from "react";
import type { Session } from "../types";
import { relativeTime } from "../lib/time";

interface Provenance {
  model?: string;
  prompt_version?: string;
  timestamp?: string;
  output_kind?: string;
}

interface GeneratedDoc {
  nodeId: string;
  text: string;
  provenance: Provenance;
}

const KIND_LABELS: Record<string, string> = {
  appeal_letter: "Appeal letter",
  dispute_letter: "Dispute letter",
  charity_application: "Charity care application",
};

function collectDocs(context: Record<string, unknown>): GeneratedDoc[] {
  const docs: GeneratedDoc[] = [];
  for (const [key, value] of Object.entries(context)) {
    if (!key.endsWith("_document") || typeof value !== "string") continue;
    const nodeId = key.slice(0, -"_document".length);
    const prov = context[`${nodeId}_provenance`];
    docs.push({
      nodeId,
      text: value,
      provenance: (prov && typeof prov === "object" ? prov : {}) as Provenance,
    });
  }
  return docs;
}

/**
 * Surfaces AI-drafted documents produced by GENERATE steps. Each carries
 * a "Needs verification" affordance (§5) — a navigator reviews and
 * approves it at the downstream approval gate before it is ever sent.
 * Per the forbidden-terms rule we say "the AI assistant", never a model id.
 */
export default function GeneratedDocuments({ caseRecord }: { caseRecord: Session }) {
  const docs = collectDocs(caseRecord.context);
  if (docs.length === 0) return null;
  return (
    <div className="space-y-3">
      {docs.map((doc) => (
        <DocumentCard key={doc.nodeId} doc={doc} />
      ))}
    </div>
  );
}

function DocumentCard({ doc }: { doc: GeneratedDoc }) {
  const [copied, setCopied] = useState(false);
  const kind = doc.provenance.output_kind || "";
  const title = KIND_LABELS[kind] || "Drafted document";
  const when = doc.provenance.timestamp ? relativeTime(doc.provenance.timestamp) : "";

  async function copy() {
    try {
      await navigator.clipboard.writeText(doc.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — no-op */
    }
  }

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
            Drafted by the AI assistant{when ? ` · ${when}` : ""}
          </p>
        </div>
        <span
          className="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded"
          style={{
            background: "rgba(234,179,8,0.15)",
            border: "1px solid rgb(234,179,8)",
            color: "var(--color-text-secondary)",
          }}
          title="AI-drafted — a person must review and approve this before it is sent"
        >
          Needs verification
        </span>
      </div>
      <div className="rounded border border-[var(--color-border)] bg-[var(--color-bg)] p-3 max-h-72 overflow-auto text-xs whitespace-pre-wrap leading-relaxed">
        {doc.text}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <p className="text-[10px] text-[var(--color-text-muted)]">
          Review this draft, then approve it at the next step to send.
        </p>
        <button
          type="button"
          onClick={copy}
          className="text-[11px] px-2 py-1 rounded border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
        >
          {copied ? "Copied" : "Copy text"}
        </button>
      </div>
    </div>
  );
}
