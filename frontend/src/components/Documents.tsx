import { useCallback, useEffect, useState } from "react";
import {
  type Artifact,
  artifactDownloadUrl,
  deleteArtifact,
  listArtifacts,
  uploadArtifact,
} from "../api";
import type { Session } from "../types";

interface Props {
  caseRecord: Session;
}

/**
 * Persistent Documents panel — lives below the StepCard in the
 * middle frame, available at every step. Solves the "navigator
 * needs to upload a doc right now" problem: file uploads are no
 * longer gated on whether the current node has a file field in
 * its input_schema.
 *
 * Files attached here go to the same case_artifacts table that
 * scripted-step uploads use. Tagged with the current pending node
 * id automatically so audit can later show which step the file
 * was added during.
 */
export default function Documents({ caseRecord }: Props) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const refresh = useCallback(async () => {
    if (!caseRecord.id) return;
    setLoading(true);
    try {
      const list = await listArtifacts(caseRecord.id);
      setArtifacts(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load documents");
    } finally {
      setLoading(false);
    }
  }, [caseRecord.id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleFiles = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await uploadArtifact(
          caseRecord.id,
          file,
          caseRecord.pending_node ?? undefined,
        );
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (artifactId: string, filename: string) => {
    if (!window.confirm(`Remove "${filename}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await deleteArtifact(artifactId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
            Documents
          </p>
          <h3 className="text-sm font-semibold mt-0.5">
            Files attached to this case
          </h3>
        </div>
        {artifacts.length > 0 && (
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {artifacts.length} file{artifacts.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {/* Drop zone */}
      <label
        className={`block border-2 border-dashed rounded-lg px-4 py-6 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-[var(--color-accent)] bg-[var(--color-bg)]"
            : "border-[var(--color-border)] hover:border-[var(--color-accent)] hover:bg-[var(--color-bg)]"
        }`}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files) {
            handleFiles(e.dataTransfer.files);
          }
        }}
      >
        <input
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.heic,.tif,.tiff,.gif,.docx,.txt"
          disabled={uploading}
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
            e.target.value = ""; // allow same file re-upload
          }}
        />
        <div className="space-y-1">
          <div className="text-2xl" aria-hidden>
            📎
          </div>
          {uploading ? (
            <p className="text-xs text-[var(--color-text-muted)]">Uploading…</p>
          ) : (
            <>
              <p className="text-sm font-medium text-[var(--color-text-primary)]">
                Drop files here or click to upload
              </p>
              <p className="text-[11px] text-[var(--color-text-muted)]">
                PDF, JPG, PNG, HEIC, TIFF, DOCX, plain text · up to 25 MB each
              </p>
            </>
          )}
        </div>
      </label>

      {error && (
        <p className="text-[11px] text-[var(--color-danger)]">{error}</p>
      )}

      {/* File list */}
      {loading && artifacts.length === 0 && (
        <p className="text-[11px] text-[var(--color-text-muted)]">Loading…</p>
      )}
      {artifacts.length === 0 && !loading && !uploading && (
        <p className="text-[11px] text-[var(--color-text-muted)] italic">
          No documents uploaded yet. Drop a bill, EOB, ID, or insurance card
          above to attach it to this case.
        </p>
      )}
      {artifacts.length > 0 && (
        <ul className="space-y-1.5">
          {artifacts.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between gap-2 px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span className="text-base flex-shrink-0" aria-hidden>
                  {iconForType(a.content_type)}
                </span>
                <div className="min-w-0 flex-1">
                  <a
                    href={artifactDownloadUrl(a.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-[var(--color-accent)] hover:underline truncate block"
                  >
                    {a.filename}
                  </a>
                  <p className="text-[10px] text-[var(--color-text-muted)]">
                    {formatBytes(a.size)} · {relativeTime(a.uploaded_at)}
                    {a.node_id && (
                      <>
                        {" · "}
                        <span className="font-mono">{a.node_id}</span>
                      </>
                    )}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(a.id, a.filename)}
                title="Remove"
                className="flex-shrink-0 text-[var(--color-text-muted)] hover:text-[var(--color-danger)] px-1 text-sm leading-none"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function iconForType(contentType: string): string {
  if (contentType.startsWith("image/")) return "🖼";
  if (contentType === "application/pdf") return "📄";
  if (contentType.includes("word")) return "📝";
  if (contentType === "text/plain") return "📃";
  return "📎";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function relativeTime(iso: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}
