import type { Session } from "../types";

interface Props {
  caseRecord: Session;
}

/**
 * Persistent "Information so far" panel that lives above the StepCard
 * in the middle frame at every step state. Shows every meaningful
 * context value the navigator has captured, filtered to hide engine
 * internals (__node_outputs, *_status, *_result, *_llm_response).
 *
 * Visible at all times so the navigator can scroll back and confirm
 * what was entered without digging through the workflow graph or the
 * raw context dump.
 */
export default function InformationSoFar({ caseRecord }: Props) {
  const visible = Object.entries(caseRecord.context).filter(([k, v]) => {
    if (k.startsWith("__")) return false;
    if (k.endsWith("_status")) return false;
    if (k.endsWith("_result")) return false;
    if (k.endsWith("_llm_response")) return false;
    if (v === null || v === undefined || v === "") return false;
    return true;
  });

  // Don't render the empty card on a brand new case — the StepCard's
  // first prompt is the only thing the user should see.
  if (visible.length === 0) {
    return null;
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          Information so far
        </p>
        <p className="text-[10px] text-[var(--color-text-muted)]">
          {visible.length} item{visible.length === 1 ? "" : "s"}
        </p>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
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
    .replace(/\bId\b/, "ID")
    .replace(/\bFpl\b/, "FPL")
    .replace(/\bSol\b/, "SOL")
    .replace(/\bAca\b/, "ACA")
    .replace(/\bChip\b/, "CHIP")
    .replace(/\bAor\b/, "AOR")
    .replace(/\bHipaa\b/, "HIPAA");
}

function formatValue(v: unknown): string {
  if (v === true) return "Yes";
  if (v === false) return "No";
  if (typeof v === "number") return v.toLocaleString();
  if (typeof v === "string") {
    if (v.length > 80) return v.slice(0, 77) + "…";
    return v;
  }
  return JSON.stringify(v);
}
