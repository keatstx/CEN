import { MODULE_CONFIGS } from "../../types";
import type { CaseSession } from "../../hooks/useCaseSession";
import { STATUS_COLOR, STATUS_LABEL } from "../../lib/status";
import { relativeTime } from "../../lib/time";

interface Props {
  session: CaseSession;
  modules: string[];
  onCaseOpened?: () => void;
}

/**
 * Sub-nav under "Executor" in the left rail. Mirrors what used to live
 * in CaseSidebar inside the center, but compact-styled for the rail.
 *
 * Project + Workflow are dropdowns; Cases is a scrollable list with the
 * + New case affordance. Selection changes drive the center via
 * `useCaseSession` (state lives at App level).
 */
export default function ExecutorSubNav({ session, modules, onCaseOpened }: Props) {
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    selectedModule,
    setSelectedModule,
    cases,
    selectedCaseId,
    setSelectedCaseId,
    loading,
    handleNewProject,
    handleNewCase,
    handleDeleteCase,
  } = session;

  return (
    <div className="space-y-3 px-3 pt-1 pb-3">
      {/* Project */}
      <div>
        <Header label="Project" actionLabel="+ New" onAction={handleNewProject} disabled={loading} />
        <select
          value={selectedProjectId ?? ""}
          onChange={(e) => setSelectedProjectId(e.target.value || null)}
          className="w-full !text-xs !py-1.5"
        >
          <option value="">— Choose —</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {/* Workflow */}
      <div>
        <Header label="Workflow" />
        <select
          value={selectedModule}
          onChange={(e) => setSelectedModule(e.target.value)}
          className="w-full !text-xs !py-1.5"
        >
          <option value="">— Choose —</option>
          {modules.map((m) => (
            <option key={m} value={m}>
              {MODULE_CONFIGS[m]?.label ?? m}
            </option>
          ))}
        </select>
      </div>

      {/* Cases */}
      <div>
        <Header
          label="Cases"
          actionLabel="+ New case"
          onAction={() => {
            handleNewCase().then(() => onCaseOpened?.());
          }}
          disabled={loading || !selectedModule || !selectedProjectId}
        />
        {cases.length === 0 ? (
          <p className="text-[10px] text-[var(--color-text-muted)] italic px-1">
            {selectedProjectId
              ? "No cases yet."
              : "Choose a project first."}
          </p>
        ) : (
          <ul className="space-y-0.5 max-h-[260px] overflow-y-auto -mx-1 px-1">
            {cases.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  onClick={() => {
                    setSelectedCaseId(c.id);
                    onCaseOpened?.();
                  }}
                  className={`w-full text-left px-2 py-1.5 pr-6 rounded text-[11px] transition-colors ${
                    selectedCaseId === c.id
                      ? "bg-[var(--color-accent-glow)] border border-[var(--color-accent)]"
                      : "hover:bg-[var(--color-surface-overlay)] border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ background: STATUS_COLOR[c.status] }}
                    />
                    <span className="font-medium truncate">
                      {c.name || c.id.slice(0, 8)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-0.5 text-[9px] text-[var(--color-text-muted)]">
                    <span className="truncate">{STATUS_LABEL[c.status]}</span>
                    <span className="ml-1">{relativeTime(c.updated_at)}</span>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(`Delete "${c.name || c.id.slice(0, 8)}"?`)) {
                      handleDeleteCase(c.id);
                    }
                  }}
                  disabled={loading}
                  title="Delete case"
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

function Header({
  label,
  actionLabel,
  onAction,
  disabled,
}: {
  label: string;
  actionLabel?: string;
  onAction?: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between mb-1">
      <label className="text-[9px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
        {label}
      </label>
      {actionLabel && onAction && (
        <button
          className="text-[10px] text-[var(--color-accent)] hover:underline disabled:opacity-50 disabled:no-underline"
          onClick={onAction}
          disabled={disabled}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
