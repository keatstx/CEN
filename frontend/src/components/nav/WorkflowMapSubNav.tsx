import { MODULE_CONFIGS } from "../../types";

interface Props {
  modules: string[];
  selectedModule: string;
  onChange: (mod: string) => void;
}

/**
 * Sub-nav under "Workflow Map" in the left rail. The module picker
 * used to sit in the center as a card; now it's a compact selector +
 * list so the center can be 100% canvas.
 */
export default function WorkflowMapSubNav({ modules, selectedModule, onChange }: Props) {
  return (
    <div className="px-3 pt-1 pb-3 space-y-2">
      <label className="text-[9px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
        Module
      </label>
      <select
        value={selectedModule}
        onChange={(e) => onChange(e.target.value)}
        className="w-full !text-xs !py-1.5"
      >
        <option value="">— Choose —</option>
        {modules.map((m) => (
          <option key={m} value={m}>
            {MODULE_CONFIGS[m]?.label ?? m}
          </option>
        ))}
      </select>

      {modules.length > 0 && (
        <ul className="space-y-0.5 mt-2">
          {modules.map((m) => (
            <li key={m}>
              <button
                onClick={() => onChange(m)}
                className={`w-full text-left px-2 py-1.5 rounded text-[11px] transition-colors truncate ${
                  selectedModule === m
                    ? "bg-[var(--color-accent-glow)] text-[var(--color-accent)] font-medium"
                    : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-primary)]"
                }`}
                title={MODULE_CONFIGS[m]?.label ?? m}
              >
                {MODULE_CONFIGS[m]?.label ?? m}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
