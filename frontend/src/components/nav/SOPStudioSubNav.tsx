import { useRef } from "react";
import type { SOPSession } from "../../hooks/useSOPSession";
import Spinner from "../ui/Spinner";

interface Props {
  session: SOPSession;
  onSelect?: () => void;
}

const STAGE_LABEL: Record<string, string> = {
  uploading: "Uploading…",
  parsing: "Reading…",
  extracting: "Extracting…",
};

const STATUS_DOT: Record<string, string> = {
  uploaded: "var(--color-text-muted)",
  parsed: "var(--color-text-secondary)",
  extracted: "var(--color-accent)",
  promoted: "var(--color-success)",
  failed: "var(--color-danger)",
};

/**
 * Sub-nav under "SOP Studio" in the left rail. Upload trigger +
 * compact SOP list. Selecting an SOP drives the center's review pane
 * via the shared `useSOPSession` hook.
 */
export default function SOPStudioSubNav({ session, onSelect }: Props) {
  const fileInput = useRef<HTMLInputElement | null>(null);
  const {
    sops,
    selectedId,
    setSelectedId,
    busy,
    uploadStage,
    handleUpload,
    handleDelete,
  } = session;

  return (
    <div className="space-y-3 px-3 pt-1 pb-3">
      <div>
        <label className="text-[9px] font-medium uppercase tracking-wider text-[var(--color-text-muted)] block mb-1">
          Upload SOP
        </label>
        <input
          ref={fileInput}
          type="file"
          accept=".md,.markdown,.docx,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUpload(f);
            if (fileInput.current) fileInput.current.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={busy}
          className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-dashed border-[var(--color-border-hover)] text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors disabled:opacity-50"
        >
          {busy && uploadStage !== "idle" ? (
            <>
              <Spinner />
              {STAGE_LABEL[uploadStage] ?? "Working…"}
            </>
          ) : (
            <>+ Choose a file</>
          )}
        </button>
      </div>

      <div>
        <label className="text-[9px] font-medium uppercase tracking-wider text-[var(--color-text-muted)] block mb-1">
          Recent uploads
        </label>
        {sops.length === 0 ? (
          <p className="text-[10px] text-[var(--color-text-muted)] italic px-1">
            Upload an SOP to get started.
          </p>
        ) : (
          <ul className="space-y-0.5 max-h-[280px] overflow-y-auto -mx-1 px-1">
            {sops.map((s) => (
              <li key={s.id} className="group relative">
                <button
                  onClick={() => {
                    setSelectedId(s.id);
                    onSelect?.();
                  }}
                  className={`w-full text-left px-2 py-1.5 pr-6 rounded text-[11px] transition-colors ${
                    selectedId === s.id
                      ? "bg-[var(--color-accent-glow)] border border-[var(--color-accent)]"
                      : "hover:bg-[var(--color-surface-overlay)] border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ background: STATUS_DOT[s.status] }}
                    />
                    <span className="font-medium truncate">{s.filename}</span>
                  </div>
                  <p className="text-[9px] text-[var(--color-text-muted)] mt-0.5 truncate">
                    {s.status}
                  </p>
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(`Delete "${s.filename}"?`)) {
                      handleDelete(s.id);
                    }
                  }}
                  disabled={busy}
                  title="Delete SOP"
                  className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 hover:text-[var(--color-danger)] text-[var(--color-text-muted)] text-[10px] px-1 rounded transition-opacity"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
