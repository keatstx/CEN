import { MODULE_CONFIGS } from "../types";

interface Props {
  modules: string[];
  selected: string;
  onSelect: (module: string) => void;
}

export default function ModuleSelector({ modules, selected, onSelect }: Props) {
  const config = selected ? MODULE_CONFIGS[selected] : null;

  return (
    <div className="space-y-3">
      <label
        htmlFor="module-select"
        className="block text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)]"
      >
        Module
      </label>
      <select
        id="module-select"
        value={selected}
        onChange={(e) => onSelect(e.target.value)}
      >
        <option value="">— Choose a module —</option>
        {modules.map((m) => (
          <option key={m} value={m}>
            {MODULE_CONFIGS[m]?.label ?? m}
          </option>
        ))}
      </select>
      {config && (
        <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">
          {config.description}
        </p>
      )}
    </div>
  );
}
