import { caseExportUrl, caseSummaryUrl } from "../api";
import type { CaseSession } from "../hooks/useCaseSession";
import Documents from "./Documents";
import InformationSoFar from "./InformationSoFar";
import StepCard from "./StepCard";
import ChatLedStep from "./chat/ChatLedStep";
import Stepper from "./Stepper";

interface Props {
  session: CaseSession;
}

/**
 * Executor — center activity for the case currently selected in the
 * left rail. Project / Workflow / Cases live in the LeftNav sub-nav
 * (see ExecutorSubNav). This component only renders the active case
 * or an empty state pointing the user to the left.
 *
 * Selection state lives at App level via `useCaseSession` so the
 * concierge can drive selections from the right rail.
 */
export default function Executor({ session }: Props) {
  const {
    selectedProjectId,
    cases,
    activeCase,
    suggestions,
    setSuggestions,
    loading,
    error,
    setError,
    handleProvideInput,
    handleApprove,
    handleRewind,
  } = session;

  return (
    <div className="space-y-4 min-h-[400px]">
      {error && (
        <div className="card border-l-4 border-l-[var(--color-danger)]">
          <p className="text-sm text-[var(--color-danger)]">
            <strong>Something went wrong.</strong> {error}
          </p>
          <button
            className="text-xs text-[var(--color-text-muted)] mt-2 hover:underline"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {!selectedProjectId && (
        <EmptyState>
          Pick a project from the left, or create a new one to get started.
        </EmptyState>
      )}

      {selectedProjectId && !activeCase && (
        <EmptyState>
          {cases.length === 0
            ? "Pick a workflow from the left and click + New case to begin."
            : "Choose a case from the left, or click + New case to start another."}
        </EmptyState>
      )}

      {activeCase && (
        <>
          <div className="card">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold truncate">
                  {activeCase.name}
                </h2>
                <p className="text-xs text-[var(--color-text-muted)] mt-0.5 font-mono">
                  {activeCase.module_name} · v{activeCase.module_version}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <a
                  href={caseSummaryUrl(activeCase.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs px-2.5 py-1.5 rounded border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors"
                  title="Open a printable summary of this case in a new tab"
                >
                  View summary
                </a>
                <a
                  href={caseExportUrl(activeCase.id)}
                  download
                  className="text-xs px-2.5 py-1.5 rounded bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
                  title="Download a ZIP packet with the summary and all uploaded documents"
                >
                  Download packet
                </a>
              </div>
            </div>
            <p className="text-[10px] font-mono text-[var(--color-text-muted)] mt-2 opacity-60">
              {activeCase.id}
            </p>
          </div>

          <Stepper caseRecord={activeCase} onRewind={handleRewind} />

          <InformationSoFar caseRecord={activeCase} />

          {activeCase.status === "AWAITING_INPUT" ? (
            <ChatLedStep
              caseRecord={activeCase}
              loading={loading}
              onSubmit={handleProvideInput}
              onApprove={handleApprove}
              suggestions={suggestions}
              onSuggestionApplied={(key) =>
                setSuggestions((prev) => prev.filter((s) => s.key !== key))
              }
            />
          ) : (
            <StepCard
              caseRecord={activeCase}
              loading={loading}
              onSubmit={handleProvideInput}
              onApprove={handleApprove}
              suggestions={suggestions}
              onSuggestionApplied={(key) =>
                setSuggestions((prev) => prev.filter((s) => s.key !== key))
              }
            />
          )}

          <Documents caseRecord={activeCase} />
        </>
      )}
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="card flex items-center justify-center min-h-[300px]">
      <p className="text-subtle text-center max-w-md px-6">{children}</p>
    </div>
  );
}
