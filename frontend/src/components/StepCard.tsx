import { useState, useEffect } from "react";
import type { InputField, Session } from "../types";
import { uploadArtifact } from "../api";

interface Props {
  caseRecord: Session;
  loading: boolean;
  onSubmit: (inputs: Record<string, unknown>) => void;
  onApprove: () => void;
}

/**
 * StepCard renders the *current* step of a case in the middle frame
 * with a real handhold UX — large step number, friendly headline,
 * descriptive subtext, contextual summary panel, and clear next action.
 *
 * - AWAITING_INPUT: form derived from pending_input_fields with field
 *   descriptions, friendly placeholders, and a primary CTA labelled
 *   for the action ("Submit and continue").
 * - AWAITING_APPROVAL: shows what's been collected so far in a summary
 *   card so the approval is informed, not blind.
 * - COMPLETED: success card with totals and outcome.
 * - FAILED: plain-language error card with a recovery hint.
 */
export default function StepCard({
  caseRecord,
  loading,
  onSubmit,
  onApprove,
}: Props) {
  const [values, setValues] = useState<Record<string, unknown>>({});

  // Reset form values when the pending node changes (new step).
  useEffect(() => {
    setValues({});
  }, [caseRecord.pending_node, caseRecord.status]);

  const stepNumber = caseRecord.executed_nodes.length + 1;

  // ─────────────── COMPLETED ───────────────
  if (caseRecord.status === "COMPLETED") {
    return (
      <div className="card space-y-4">
        <div className="flex items-start gap-3">
          <div
            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white text-lg font-bold"
            style={{ background: "var(--color-success)" }}
          >
            ✓
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
              All steps complete
            </p>
            <h3 className="text-lg font-semibold mt-0.5">
              You're done with this case
            </h3>
          </div>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
          The workflow finished successfully. {caseRecord.executed_nodes.length}{" "}
          step{caseRecord.executed_nodes.length === 1 ? "" : "s"} ran from start
          to finish. You can review everything that was collected in the
          "Information so far" panel above, or start a new case for the same
          patient from the left panel.
        </p>
      </div>
    );
  }

  // ─────────────── FAILED ───────────────
  if (caseRecord.status === "FAILED") {
    return (
      <div
        className="card space-y-4 border-l-4"
        style={{ borderLeftColor: "var(--color-danger)" }}
      >
        <div className="flex items-start gap-3">
          <div
            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white text-lg font-bold"
            style={{ background: "var(--color-danger)" }}
          >
            !
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
              Workflow stopped
            </p>
            <h3 className="text-lg font-semibold mt-0.5">
              Something went wrong
            </h3>
          </div>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
          The workflow stopped before it could finish. Start a new case from
          the left panel to try again, or ask the AI Concierge on the right if
          you're not sure what happened.
        </p>
      </div>
    );
  }

  // ─────────────── AWAITING_APPROVAL ───────────────
  if (caseRecord.status === "AWAITING_APPROVAL") {
    return (
      <div className="card space-y-5">
        <StepHeader
          stepNumber={stepNumber}
          eyebrow="Your turn"
          title="Review and approve"
          subtitle="The workflow needs your sign-off before it can continue. Take a quick look at what's been collected so far, then approve to move on."
          nodeId={caseRecord.pending_node}
        />

        <CollectedSummary context={caseRecord.context} />

        <button
          className="btn btn-primary w-full text-sm py-3"
          onClick={onApprove}
          disabled={loading}
        >
          {loading ? "Working…" : "Looks good — approve and continue →"}
        </button>
      </div>
    );
  }

  // ─────────────── AWAITING_INPUT ───────────────
  if (caseRecord.status === "AWAITING_INPUT") {
    const fields = caseRecord.pending_input_fields ?? [];
    const allRequiredFilled = fields
      .filter((f) => f.required)
      .every((f) => {
        const v = values[f.key];
        return v !== undefined && v !== null && v !== "";
      });

    const stepTitle = fields[0]?.label || "We need a bit more information";
    const stepSubtitle = fields[0]?.description
      ? "Fill in the details below to continue."
      : "Take a moment to provide the information below — it'll be used in later steps.";

    return (
      <div className="card space-y-5">
        <StepHeader
          stepNumber={stepNumber}
          eyebrow="Your turn"
          title={stepTitle}
          subtitle={stepSubtitle}
          nodeId={caseRecord.pending_node}
        />

        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (allRequiredFilled && !loading) onSubmit(values);
          }}
        >
          {fields.map((field, idx) => (
            <FieldInput
              key={field.key}
              field={field}
              isFirst={idx === 0}
              value={values[field.key]}
              caseId={caseRecord.id}
              nodeId={caseRecord.pending_node ?? undefined}
              onChange={(v) =>
                setValues((prev) => ({ ...prev, [field.key]: v }))
              }
            />
          ))}
          <button
            type="submit"
            className="btn btn-primary w-full text-sm py-3 mt-2"
            disabled={!allRequiredFilled || loading}
          >
            {loading ? "Working…" : "Submit and continue →"}
          </button>
          {!allRequiredFilled && (
            <p className="text-[11px] text-[var(--color-text-muted)] text-center">
              Fill in the required fields to continue.
            </p>
          )}
        </form>
      </div>
    );
  }

  // ─────────────── ACTIVE (transient) ───────────────
  return (
    <div className="card flex items-center justify-center min-h-[200px]">
      <div className="text-center space-y-2">
        <div className="inline-block w-6 h-6 border-2 border-[var(--color-text-muted)] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[var(--color-text-muted)]">
          Working on the next step…
        </p>
      </div>
    </div>
  );
}

// ─────────────── Sub-components ───────────────

function StepHeader({
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

/**
 * Renders the case context as a friendly key/value summary panel.
 * Filters out internal engine state (anything starting with __ or
 * ending in _status / _result / _llm_response) so the navigator only
 * sees what they actually entered.
 */
function CollectedSummary({ context }: { context: Record<string, unknown> }) {
  const visible = Object.entries(context).filter(([k, v]) => {
    if (k.startsWith("__")) return false;
    if (k.endsWith("_status")) return false;
    if (k.endsWith("_result")) return false;
    if (k.endsWith("_llm_response")) return false;
    if (v === null || v === undefined || v === "") return false;
    return true;
  });

  if (visible.length === 0) {
    return (
      <div className="bg-[var(--color-bg)] rounded-lg px-4 py-3 text-xs text-[var(--color-text-muted)] italic">
        No information collected yet for this case.
      </div>
    );
  }

  return (
    <div className="bg-[var(--color-bg)] rounded-lg px-4 py-3 space-y-2">
      <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
        Information collected so far
      </p>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
        {visible.map(([k, v]) => (
          <div key={k} className="flex flex-col">
            <dt className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wide">
              {humanizeKey(k)}
            </dt>
            <dd className="text-xs text-[var(--color-text-primary)] font-medium">
              {formatValue(v)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bDob\b/, "DOB")
    .replace(/\bSsn\b/, "SSN")
    .replace(/\bId\b/, "ID");
}

function formatValue(v: unknown): string {
  if (v === true) return "Yes";
  if (v === false) return "No";
  if (typeof v === "number") return v.toLocaleString();
  if (typeof v === "string") {
    // Truncate long strings
    if (v.length > 80) return v.slice(0, 77) + "…";
    return v;
  }
  return JSON.stringify(v);
}

function FieldInput({
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
  // The first field's label is already shown as the step title — for
  // the first field we render the field without re-showing its label
  // (just the input + description).
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
    return (
      <div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            className="w-4 h-4"
          />
          <span>{field.label}</span>
          {field.required && (
            <span className="text-[var(--color-danger)] ml-0.5">*</span>
          )}
        </label>
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

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
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
      <input
        type="file"
        onChange={handleFile}
        disabled={uploading}
        className="w-full text-xs"
        accept=".pdf,.png,.jpg,.jpeg,.heic,.tif,.tiff,.gif,.docx,.txt"
      />
      {uploading && (
        <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
          Uploading…
        </p>
      )}
      {uploadedName && !uploading && (
        <p className="text-[11px] text-[var(--color-success)] mt-1">
          ✓ Uploaded: {uploadedName}
        </p>
      )}
      {uploadError && (
        <p className="text-[11px] text-[var(--color-danger)] mt-1">
          {uploadError}
        </p>
      )}
      {description}
      {value && !uploadedName && (
        <p className="text-[10px] font-mono text-[var(--color-text-muted)] mt-1">
          Already uploaded
        </p>
      )}
    </div>
  );
}
