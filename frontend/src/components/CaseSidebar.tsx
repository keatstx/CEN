import type { Project, Session } from "../types";
import { MODULE_CONFIGS } from "../types";
import { STATUS_COLOR, STATUS_LABEL } from "../lib/status";
import { relativeTime } from "../lib/time";

interface Props {
  projects: Project[];
  selectedProjectId: string | null;
  onSelectProject: (id: string) => void;
  onNewProject: () => void;

  modules: string[];
  selectedModule: string;
  onSelectModule: (mod: string) => void;

  cases: Session[];
  selectedCaseId: string | null;
  onSelectCase: (id: string) => void;
  onNewCase: () => void;
  onDeleteCase: (id: string) => void;
  loading: boolean;
}

export default function CaseSidebar({
  projects,
  selectedProjectId,
  onSelectProject,
  onNewProject,
  modules,
  selectedModule,
  onSelectModule,
  cases,
  selectedCaseId,
  onSelectCase,
  onNewCase,
  onDeleteCase,
  loading,
}: Props) {
  return (
    <div className="space-y-4">
      {/* Project picker */}
      <div className="card space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
            Project
          </label>
          <button
            className="text-[11px] text-[var(--color-accent)] hover:underline"
            onClick={onNewProject}
            disabled={loading}
          >
            + New
          </button>
        </div>
        <select
          value={selectedProjectId ?? ""}
          onChange={(e) => onSelectProject(e.target.value)}
          className="w-full"
        >
          <option value="">— Choose a project —</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {/* Module picker */}
      <div className="card space-y-2">
        <label className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          Workflow
        </label>
        <select
          value={selectedModule}
          onChange={(e) => onSelectModule(e.target.value)}
          className="w-full"
        >
          <option value="">— Choose a workflow —</option>
          {modules.map((m) => (
            <option key={m} value={m}>
              {MODULE_CONFIGS[m]?.label ?? m}
            </option>
          ))}
        </select>
      </div>

      {/* Case list */}
      <div className="card space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
            Cases
          </label>
          <button
            className="text-[11px] text-[var(--color-accent)] hover:underline disabled:opacity-50 disabled:no-underline"
            onClick={onNewCase}
            disabled={loading || !selectedModule || !selectedProjectId}
          >
            + New case
          </button>
        </div>
        {cases.length === 0 ? (
          <p className="text-[11px] text-[var(--color-text-muted)] italic">
            {selectedProjectId
              ? "No cases yet. Click + New case to start your first workflow."
              : "Choose a project to see its cases."}
          </p>
        ) : (
          <ul className="space-y-1 max-h-[280px] overflow-y-auto -mx-1 px-1">
            {cases.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  onClick={() => onSelectCase(c.id)}
                  className={`w-full text-left px-2 py-1.5 pr-7 rounded text-xs transition-colors ${
                    selectedCaseId === c.id
                      ? "bg-[var(--color-bg)] border border-[var(--color-accent)]"
                      : "hover:bg-[var(--color-bg)] border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ background: STATUS_COLOR[c.status] }}
                    />
                    <span className="font-medium truncate">{c.name || c.id.slice(0, 8)}</span>
                  </div>
                  <div className="flex items-center justify-between mt-0.5 text-[10px] text-[var(--color-text-muted)]">
                    <span>{STATUS_LABEL[c.status]}</span>
                    <span>{relativeTime(c.updated_at)}</span>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (
                      window.confirm(
                        `Delete "${c.name || c.id.slice(0, 8)}"? This cannot be undone.`,
                      )
                    ) {
                      onDeleteCase(c.id);
                    }
                  }}
                  disabled={loading}
                  title="Delete case"
                  className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 hover:text-[var(--color-danger)] text-[var(--color-text-muted)] text-xs px-1.5 py-0.5 rounded transition-opacity"
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
