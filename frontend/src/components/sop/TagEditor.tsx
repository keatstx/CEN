import { useMemo, useState } from "react";
import { patchSOPNode, type DraftEditResponse } from "../../api";
import type { TagVocabulary } from "../../types";

const OPEN_FACETS = new Set(["attribute"]);

/** Mirror of backend cen.core.tags.is_known_tag so the editor can flag
 *  out-of-vocabulary tags before the draft validator does. */
function isKnownTag(tag: string, vocab: TagVocabulary): boolean {
  const idx = tag.indexOf(":");
  if (idx <= 0 || idx === tag.length - 1) return false;
  const facet = tag.slice(0, idx).trim();
  const value = tag.slice(idx + 1).trim();
  if (!facet || !value) return false;
  if (OPEN_FACETS.has(facet)) return true;
  return (vocab[facet] ?? []).includes(value);
}

interface Props {
  sopId: string;
  nodeId: string;
  tags: string[];
  vocabulary: TagVocabulary;
  onDraftUpdated: (updated: DraftEditResponse) => void;
}

/** Per-step tag chips + add control, wired to the draft-node PATCH.
 *  The first node-editing surface in SOP Studio: a human curates the
 *  structurally auto-assigned tags before promote. */
export function TagEditor({ sopId, nodeId, tags, vocabulary, onDraftUpdated }: Props) {
  const [draftInput, setDraftInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const suggestions = useMemo(() => {
    const out: string[] = [];
    for (const [facet, values] of Object.entries(vocabulary)) {
      for (const v of values) out.push(`${facet}:${v}`);
    }
    return out.filter((s) => !tags.includes(s));
  }, [vocabulary, tags]);

  async function commit(next: string[]) {
    setBusy(true);
    setError(null);
    try {
      const res = await patchSOPNode(sopId, nodeId, { tags: next });
      onDraftUpdated(res);
    } catch {
      setError("Couldn't save tags. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function add() {
    const tag = draftInput.trim();
    if (!tag || tags.includes(tag)) {
      setDraftInput("");
      return;
    }
    setDraftInput("");
    void commit([...tags, tag]);
  }

  function remove(tag: string) {
    void commit(tags.filter((t) => t !== tag));
  }

  const listId = `tagvocab-${nodeId}`;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        {tags.length === 0 && (
          <span className="text-[10px] text-[var(--color-text-muted)]">No tags</span>
        )}
        {tags.map((tag) => {
          const known = isKnownTag(tag, vocabulary);
          return (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono"
              style={{
                background: known ? "var(--color-bg)" : "rgba(234,179,8,0.15)",
                border: `1px solid ${known ? "var(--color-border)" : "rgb(234,179,8)"}`,
              }}
              title={known ? tag : `${tag} — not in the project vocabulary (allowed)`}
            >
              {tag}
              <button
                type="button"
                aria-label={`Remove tag ${tag}`}
                disabled={busy}
                onClick={() => remove(tag)}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-error)] leading-none"
              >
                ×
              </button>
            </span>
          );
        })}
      </div>
      <div className="flex items-center gap-1">
        <input
          type="text"
          list={listId}
          value={draftInput}
          disabled={busy}
          placeholder="facet:value"
          aria-label={`Add a tag to step ${nodeId}`}
          onChange={(e) => setDraftInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          className="w-32 px-1.5 py-0.5 text-[10px] font-mono border border-[var(--color-border)] rounded"
        />
        <datalist id={listId}>
          {suggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <button
          type="button"
          disabled={busy || !draftInput.trim()}
          onClick={add}
          className="text-[10px] px-1.5 py-0.5 rounded border border-[var(--color-border)] disabled:opacity-40"
        >
          Add
        </button>
      </div>
      {error && (
        <span className="text-[10px]" style={{ color: "var(--color-error)" }}>
          {error}
        </span>
      )}
    </div>
  );
}
