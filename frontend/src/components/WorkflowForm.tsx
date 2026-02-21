import { useState } from "react";
import { MODULE_CONFIGS, type FieldConfig } from "../types";

interface Props {
  moduleName: string;
  loading: boolean;
  onExecute: (context: Record<string, unknown>) => void;
}

export default function WorkflowForm({ moduleName, loading, onExecute }: Props) {
  const config = MODULE_CONFIGS[moduleName];
  const [values, setValues] = useState<Record<string, unknown>>({});

  if (!config) return null;

  const setValue = (key: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const context: Record<string, unknown> = {};
    for (const field of config.fields) {
      const v = values[field.key];
      if (field.type === "number") {
        context[field.key] = v !== undefined && v !== "" ? Number(v) : 0;
      } else if (field.type === "boolean") {
        context[field.key] = v === true;
      } else {
        context[field.key] = v ?? "";
      }
    }
    onExecute(context);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
        Patient Context
      </h3>
      {config.fields.map((field) => (
        <FieldInput
          key={field.key}
          field={field}
          value={values[field.key]}
          onChange={(v) => setValue(field.key, v)}
        />
      ))}
      <button type="submit" disabled={loading}>
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Executing…
          </span>
        ) : (
          "Execute Workflow"
        )}
      </button>
    </form>
  );
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: FieldConfig;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (field.type === "boolean") {
    return (
      <label className="flex items-center gap-3 text-sm text-[var(--color-text-secondary)] cursor-pointer group">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4 rounded"
        />
        <span className="group-hover:text-[var(--color-text-primary)] transition-colors">
          {field.label}
        </span>
      </label>
    );
  }

  if (field.type === "select" && field.options) {
    return (
      <div className="space-y-1.5">
        <label className="block text-xs text-[var(--color-text-secondary)]">{field.label}</label>
        <select
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          required={field.required}
        >
          <option value="">— Select —</option>
          {field.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (field.type === "text" && field.key.includes("summary")) {
    return (
      <div className="space-y-1.5">
        <label className="block text-xs text-[var(--color-text-secondary)]">{field.label}</label>
        <textarea
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          required={field.required}
        />
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <label className="block text-xs text-[var(--color-text-secondary)]">{field.label}</label>
      <input
        type={field.type === "number" ? "number" : "text"}
        value={(value as string | number) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        required={field.required}
      />
    </div>
  );
}
