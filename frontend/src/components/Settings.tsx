interface Props {
  onResetLayout: () => void;
}

export default function Settings({ onResetLayout }: Props) {
  return (
    <section className="max-w-2xl">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold text-[var(--color-text-primary)]">Settings</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Workspace preferences for this device. Account-level settings arrive with sign-in.
        </p>
      </header>

      <div className="card">
        <h3 className="text-base font-medium text-[var(--color-text-primary)]">Layout</h3>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          The navigation and assistant panels remember whether you had them open or closed. Reset
          the memory if you want to start fresh.
        </p>
        <button
          type="button"
          onClick={onResetLayout}
          className="mt-4 inline-flex items-center px-4 py-2 rounded-md border border-[var(--color-border)] text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          Reset panel layout
        </button>
      </div>
    </section>
  );
}
