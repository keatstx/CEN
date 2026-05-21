// TODO(rbac): Once `useCurrentUser` is wired through to here and real
// per-user auth lands, replace USER_DISPLAY_NAME with `user.name`. Until
// then the literal string keeps the FlowUX welcome warm without leaking
// a real user record. See radiant-giggling-dusk.md Risk #1.
const USER_DISPLAY_NAME = "Charles";

interface Props {
  onContinue: () => void;
  onStart: () => void;
}

export default function WelcomeScreen({ onContinue, onStart }: Props) {
  return (
    <section className="max-w-4xl mx-auto pt-6">
      <div
        className="relative overflow-hidden rounded-2xl border border-[var(--color-border)] p-10 sm:p-12"
        style={{
          background:
            "linear-gradient(135deg, var(--color-primary) 0%, #1a1a1a 100%)",
        }}
      >
        <BrandAccent />
        <div className="relative z-10 max-w-xl">
          <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-accent)] font-semibold">
            Concitor · FlowUX Studio
          </p>
          <h1 className="mt-4 text-3xl sm:text-4xl font-semibold text-white leading-tight">
            Welcome back, {USER_DISPLAY_NAME}.
            <br />
            <span className="text-[var(--color-accent)]">Ready to get started?</span>
          </h1>
          <p className="mt-4 text-sm sm:text-base text-gray-300 leading-relaxed">
            Pick up a case you've been working on, or kick off a brand-new one. The
            assistant on the right is here whenever you need a hand — ask anything.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row gap-3">
            <button
              type="button"
              onClick={onContinue}
              className="px-6 py-3 rounded-md bg-[var(--color-accent)] text-white text-sm font-semibold hover:bg-[var(--color-accent-hover)] transition-colors shadow-lg shadow-orange-500/20"
            >
              Continue a case
            </button>
            <button
              type="button"
              onClick={onStart}
              className="px-6 py-3 rounded-md border border-white/30 bg-white/5 backdrop-blur text-white text-sm font-semibold hover:bg-white/10 transition-colors"
            >
              Start a new case
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8">
        <HighlightCard
          title="Workflow co-pilot"
          body="One step at a time. The assistant walks you through every field, every approval."
        />
        <HighlightCard
          title="Audit-ready"
          body="Every action recorded. Every AI answer cited. Nothing happens off the record."
        />
        <HighlightCard
          title="Plain language"
          body="Eighth-grade reading level. No jargon. No HTTP codes. Just what to do next."
        />
      </div>
    </section>
  );
}

function HighlightCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{title}</h3>
      <p className="mt-2 text-xs text-[var(--color-text-secondary)] leading-relaxed">{body}</p>
    </div>
  );
}

function BrandAccent() {
  // Decorative orange brushstroke in the bottom-right of the hero.
  return (
    <svg
      viewBox="0 0 400 300"
      className="absolute -right-12 -bottom-12 w-[420px] h-[320px] opacity-90 pointer-events-none"
      aria-hidden
    >
      <defs>
        <linearGradient id="cen-welcome-accent" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.65" />
          <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <path
        d="M40 240 Q 180 60 380 100 L 400 300 L 40 300 Z"
        fill="url(#cen-welcome-accent)"
      />
      <circle cx="320" cy="80" r="6" fill="var(--color-accent)" opacity="0.6" />
      <circle cx="280" cy="40" r="3" fill="var(--color-accent)" opacity="0.4" />
    </svg>
  );
}
