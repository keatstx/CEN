import { useState, useEffect } from "react";
import type { InputField, Session } from "../types";

interface Props {
  caseRecord: Session;
  loading: boolean;
  onSubmit: (inputs: Record<string, unknown>) => void;
  onApprove: () => void;
}

/**
 * StepCard renders the *current* step of a case in the middle frame.
 *
 * - AWAITING_INPUT: renders the schema as a form, "Continue" submits.
 * - AWAITING_APPROVAL: renders an approval gate with "Review and approve".
 * - COMPLETED: shows the final outcome and a done state.
 * - FAILED: shows an error state with the failure reason.
 * - ACTIVE: should rarely render (engine is mid-execution); shows a
 *   "Working…" placeholder so the user knows something is happening.
 */
export default function StepCard({ caseRecord, loading, onSubmit, onApprove }: Props) {
  const [values, setValues] = useState<Record<string, unknown>>({});

  // Reset form values when the pending node changes (new step).
  useEffect(() => {
    setValues({});
  }, [caseRecord.pending_node, caseRecord.status]);

  if (caseRecord.status === "COMPLETED") {
    return (
      <div className="card space-y-3">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-[var(--color-success)]" />
          <h3 className="text-sm font-semibold">Done</h3>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)]">
          This case is complete. {caseRecord.executed_nodes.length} steps ran.
        </p>
      </div>
    );
  }

  if (caseRecord.status === "FAILED") {
    return (
      <div className="card space-y-3">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-[var(--color-danger)]" />
          <h3 className="text-sm font-semibold">Something went wrong</h3>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)]">
          The workflow stopped with an error. Start a new case to try again.
        </p>
      </div>
    );
  }

  if (caseRecord.status === "AWAITING_APPROVAL") {
    return (
      <div className="card space-y-4">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
            Step {caseRecord.executed_nodes.length}
          </p>
          <h3 className="text-base font-semibold mt-1">Review and approve</h3>
          <p className="text-xs text-[var(--color-text-muted)] font-mono mt-1">
            {caseRecord.pending_node}
          </p>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)]">
          The workflow is waiting for your approval to continue. Review the
          information collected so far before proceeding.
        </p>
        <button
          className="btn btn-primary w-full"
          onClick={onApprove}
          disabled={loading}
        >
          {loading ? "Working…" : "Review and approve"}
        </button>
      </div>
    );
  }

  if (caseRecord.status === "AWAITING_INPUT") {
    const fields = caseRecord.pending_input_fields ?? [];
    const allRequiredFilled = fields
      .filter((f) => f.required)
      .every((f) => {
        const v = values[f.key];
        return v !== undefined && v !== null && v !== "";
      });

    return (
      <div className="card space-y-4">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
            Step {caseRecord.executed_nodes.length + 1}
          </p>
          <h3 className="text-base font-semibold mt-1">
            {fields[0]?.label || "We need a bit more information"}
          </h3>
          <p className="text-xs text-[var(--color-text-muted)] font-mono mt-1">
            {caseRecord.pending_node}
          </p>
        </div>

        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (allRequiredFilled && !loading) onSubmit(values);
          }}
        >
          {fields.map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              value={values[field.key]}
              onChange={(v) =>
                setValues((prev) => ({ ...prev, [field.key]: v }))
              }
            />
          ))}
          <button
            type="submit"
            className="btn btn-primary w-full mt-2"
            disabled={!allRequiredFilled || loading}
          >
            {loading ? "Working…" : "Continue"}
          </button>
        </form>
      </div>
    );
  }

  // ACTIVE — engine is mid-execution. Should be a brief state.
  return (
    <div className="card flex items-center justify-center min-h-[200px]">
      <p className="text-sm text-[var(--color-text-muted)]">Working…</p>
    </div>
  );
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: InputField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const labelEl = (
    <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
      {field.label}
      {field.required && <span className="text-[var(--color-danger)] ml-0.5">*</span>}
    </label>
  );

  const description = field.description && (
    <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
      {field.description}
    </p>
  );

  if (field.type === "boolean") {
    return (
      <div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span>{field.label}</span>
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
          className="w-full"
        >
          <option value="">— Choose —</option>
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
          className="w-full"
          placeholder={field.type === "currency" ? "$0.00" : ""}
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
          className="w-full"
        />
        {description}
      </div>
    );
  }

  if (field.type === "file") {
    return (
      <div>
        {labelEl}
        <input
          type="file"
          disabled
          className="w-full text-xs"
        />
        <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
          File uploads coming soon — for now, please describe the document in the next text field.
        </p>
      </div>
    );
  }

  // Default: text
  return (
    <div>
      {labelEl}
      <textarea
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className="w-full"
        placeholder="Type your answer…"
      />
      {description}
    </div>
  );
}
