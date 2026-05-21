import type { User } from "../types";

interface Props {
  user: User | null;
  loading: boolean;
}

export default function Profile({ user, loading }: Props) {
  return (
    <section className="max-w-2xl">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold text-[var(--color-text-primary)]">Profile</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Your operator identity. Real accounts arrive with sign-in.
        </p>
      </header>

      <div className="card">
        {loading && (
          <p className="text-sm text-[var(--color-text-muted)]">Loading your profile…</p>
        )}
        {!loading && !user && (
          <p className="text-sm text-[var(--color-text-muted)]">
            We couldn't load your profile right now. Try refreshing the page.
          </p>
        )}
        {!loading && user && (
          <dl className="space-y-3">
            <Row label="Name">{user.name || "—"}</Row>
            <Row label="Operator ID">
              <code className="text-xs bg-[var(--color-surface-overlay)] px-2 py-0.5 rounded">
                {user.id}
              </code>
            </Row>
            <Row label="Access level">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  user.is_admin
                    ? "bg-[var(--color-accent-glow)] text-[var(--color-accent)]"
                    : "bg-[var(--color-surface-overlay)] text-[var(--color-text-secondary)]"
                }`}
              >
                {user.is_admin ? "Admin" : "Navigator"}
              </span>
            </Row>
          </dl>
        )}
      </div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-sm text-[var(--color-text-secondary)]">{label}</dt>
      <dd className="text-sm text-[var(--color-text-primary)]">{children}</dd>
    </div>
  );
}
