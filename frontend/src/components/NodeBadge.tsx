const TYPE_STYLES: Record<string, string> = {
  ACTION:
    "bg-[var(--color-blue-muted)] text-[var(--color-blue)] border-[var(--color-blue)]40",
  CONDITION:
    "bg-[var(--color-warning-muted)] text-[var(--color-warning)] border-[var(--color-warning)]40",
  HANDOFF:
    "bg-[var(--color-success-muted)] text-[var(--color-success)] border-[var(--color-success)]40",
};

interface Props {
  nodeId: string;
  nodeType?: string;
}

export default function NodeBadge({ nodeId, nodeType }: Props) {
  const styles = TYPE_STYLES[nodeType ?? "ACTION"] ?? TYPE_STYLES.ACTION;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-mono font-medium border ${styles}`}
    >
      {nodeId}
    </span>
  );
}
