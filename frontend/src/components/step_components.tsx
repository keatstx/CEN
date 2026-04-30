import { useState } from "react";
import type { InputField } from "../types";
import { uploadArtifact } from "../api";

/**
 * Subcomponents extracted from StepCard.tsx per CLAUDE.md §4.9.
 * StepHeader, FieldInput, and FileFieldInput live here so the main
 * StepCard file stays focused on the per-status branches.
 *
 * The exports are intentionally a small, stable surface — only the
 * three components consumed by StepCard. New input types should be
 * added here, not back in the main file.
 */

export function StepHeader({
  stepNumber,
  eyebrow,
  title,
  subtitle,
  nodeId,
}: {
  stepNumber: number;
  eyebrow: string;
  title: string;
  subtitle: string;
  nodeId: string | null;
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
        style={{ background: "var(--color-accent)" }}
      >
        {stepNumber}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          {eyebrow} · Step {stepNumber}
        </p>
        <h3 className="text-lg font-semibold mt-0.5 leading-tight">{title}</h3>
        <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed mt-1">
          {subtitle}
        </p>
        {nodeId && (
          <p className="text-[10px] font-mono text-[var(--color-text-muted)] mt-1 opacity-60">
            {nodeId}
          </p>
        )}
      </div>
    </div>
  );
}

export function FieldInput({
  field,
  isFirst,
  value,
  caseId,
  nodeId,
  onChange,
}: {
  field: InputField;
  isFirst: boolean;
  value: unknown;
  caseId: string;
  nodeId?: string;
  onChange: (v: unknown) => void;
}) {
  const labelEl = !isFirst && (
    <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
      {field.label}
      {field.required && (
        <span className="text-[var(--color-danger)] ml-0.5">*</span>
      )}
    </label>
  );

  const description = field.description && (
    <p className="text-[11px] text-[var(--color-text-muted)] mt-1 leading-snug">
      {field.description}
    </p>
  );

  if (field.type === "boolean") {
    const isYes = value === true;
    const isNo = value === false;
    return (
      <div>
        {labelEl ?? (
          <p className="text-xs font-medium text-[var(--color-text-secondary)] mb-2">
            {field.label}
            {field.required && (
              <span className="text-[var(--color-danger)] ml-0.5">*</span>
            )}
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => onChange(true)}
            className={`px-3 py-2 rounded border text-sm font-medium transition-colors ${
              isYes
                ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)]"
                : "bg-[var(--color-bg)] text-[var(--color-text-primary)] border-[var(--color-border)] hover:border-[var(--color-accent)]"
            }`}
          >
            Yes
          </button>
          <button
            type="button"
            onClick={() => onChange(false)}
            className={`px-3 py-2 rounded border text-sm font-medium transition-colors ${
              isNo
                ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)]"
                : "bg-[var(--color-bg)] text-[var(--color-text-primary)] border-[var(--color-border)] hover:border-[var(--color-accent)]"
            }`}
          >
            No
          </button>
        </div>
        {description}
      </div>
    );
  }

  if (field.type === "select" && field.options) {
    return (
      <div>
        {labelEl}
        <select
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="w-full text-sm py-2"
        >
          <option value="">— Choose one —</option>
          {field.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {description}
      </div>
    );
  }

  if (field.type === "number" || field.type === "currency") {
    return (
      <div>
        {labelEl}
        <input
          type="number"
          inputMode="decimal"
          value={(value as number | string) ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            onChange(v === "" ? null : Number(v));
          }}
          className="w-full text-sm py-2"
          placeholder={field.type === "currency" ? "0.00" : "Enter a number"}
        />
        {description}
      </div>
    );
  }

  if (field.type === "date") {
    return (
      <div>
        {labelEl}
        <input
          type="date"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="w-full text-sm py-2"
        />
        {description}
      </div>
    );
  }

  if (field.type === "file") {
    return (
      <FileFieldInput
        value={value as string | null}
        caseId={caseId}
        nodeId={nodeId}
        onChange={onChange}
        labelEl={labelEl}
        description={description}
      />
    );
  }

  // Default: text — single line for short labels, textarea for free-form
  const isMultiline = (field.label?.length ?? 0) > 30 || isFirst;
  if (isMultiline) {
    return (
      <div>
        {labelEl}
        <textarea
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="w-full text-sm"
          placeholder="Type your answer here…"
        />
        {description}
      </div>
    );
  }
  return (
    <div>
      {labelEl}
      <input
        type="text"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full text-sm py-2"
        placeholder="Type your answer…"
      />
      {description}
    </div>
  );
}

function FileFieldInput({
  value,
  caseId,
  nodeId,
  onChange,
  labelEl,
  description,
}: {
  value: string | null;
  caseId: string;
  nodeId?: string;
  onChange: (v: unknown) => void;
  labelEl: React.ReactNode;
  description: React.ReactNode;
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedName, setUploadedName] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const upload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const artifact = await uploadArtifact(caseId, file, nodeId);
      onChange(artifact.id);
      setUploadedName(artifact.filename);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      {labelEl}
      <label
        className={`block border-2 border-dashed rounded-lg px-4 py-5 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-[var(--color-accent)] bg-[var(--color-bg)]"
            : uploadedName
              ? "border-[var(--color-success)] bg-[var(--color-bg)]"
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
          const file = e.dataTransfer.files?.[0];
          if (file) upload(file);
        }}
      >
        <input
          type="file"
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.heic,.tif,.tiff,.gif,.docx,.txt"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload(file);
          }}
        />
        {uploading && (
          <p className="text-xs text-[var(--color-text-muted)]">Uploading…</p>
        )}
        {!uploading && uploadedName && (
          <p className="text-xs text-[var(--color-success)] font-medium">
            ✓ Uploaded: {uploadedName}
          </p>
        )}
        {!uploading && !uploadedName && (
          <>
            <div className="text-xl mb-1" aria-hidden>
              📎
            </div>
            <p className="text-xs font-medium text-[var(--color-text-primary)]">
              Drop a file here or click to upload
            </p>
            <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
              PDF, image, or DOCX
            </p>
          </>
        )}
      </label>
      {uploadError && (
        <p className="text-[11px] text-[var(--color-danger)] mt-1">
          {uploadError}
        </p>
      )}
      {description}
      {value && !uploadedName && (
        <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
          ✓ A file is already attached for this field.
        </p>
      )}
    </div>
  );
}
