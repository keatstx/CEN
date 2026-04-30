import { useMemo, useRef, useState, useEffect } from "react";
import type { AOPDefinition, ValidationIssue } from "../../types";
import {
  NODE_COLORS,
  NODE_W,
  NODE_H,
  edgeAnchors,
  layoutDAG,
  type LayoutNode,
} from "../dag/layout";

interface Props {
  draft: AOPDefinition;
  issues: ValidationIssue[];
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
}

/**
 * Visual representation of an SOP draft with issue overlays.
 *
 * - Nodes carry red rings when an error references them, yellow rings
 *   for warnings, and a strikethrough/gray opacity when unreachable.
 * - Edges that participate in a cycle are dashed red.
 * - Branch pointers that target a node not in the draft are drawn as
 *   dangling red arrows ending at a "?" terminal.
 * - Click a node -> calls onSelectNode(id) so the parent can scroll
 *   the validation panel to its issues. Re-click to clear selection.
 *
 * Fit-to-screen by default — no pan/zoom for v1. SOPs typically have
 * 10–40 nodes; the live DAG Viewer (with pan/zoom) handles the
 * 100+-node case.
 */
export default function DraftDAG({
  draft,
  issues,
  selectedNodeId,
  onSelectNode,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const c = containerRef.current;
    if (!c || typeof ResizeObserver === "undefined") return;
    const update = () => setSize({ w: c.clientWidth, h: c.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(c);
    return () => ro.disconnect();
  }, []);

  const layout = useMemo(
    () => layoutDAG(draft.nodes, draft.edges, "TB"),
    [draft],
  );
  const posMap = useMemo(
    () => new Map(layout.positioned.map((ln) => [ln.id, ln])),
    [layout],
  );

  // Group issues by node id for quick overlay lookups.
  const issuesByNode = useMemo(() => {
    const map = new Map<string, ValidationIssue[]>();
    for (const issue of issues) {
      if (!issue.node_id) continue;
      const list = map.get(issue.node_id) ?? [];
      list.push(issue);
      map.set(issue.node_id, list);
    }
    return map;
  }, [issues]);

  const cycleNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const issue of issues) {
      if (
        issue.severity === "error" &&
        issue.node_id &&
        issue.message.toLowerCase().includes("cycle")
      ) {
        ids.add(issue.node_id);
      }
    }
    return ids;
  }, [issues]);

  const unreachableNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const issue of issues) {
      if (
        issue.node_id &&
        issue.message.toLowerCase().includes("unreachable")
      ) {
        ids.add(issue.node_id);
      }
    }
    return ids;
  }, [issues]);

  const validNodeIds = useMemo(
    () => new Set(draft.nodes.map((n) => n.id)),
    [draft],
  );

  // Fit-to-screen scale: shrink so the SVG fits the container width.
  const scale =
    size.w > 0 ? Math.min(1, size.w / Math.max(layout.svgW, 1)) : 1;
  const scaledW = layout.svgW * scale;
  const scaledH = layout.svgH * scale;

  return (
    <div
      ref={containerRef}
      className="card overflow-hidden p-0"
      style={{ minHeight: 240 }}
    >
      <div
        className="px-3 py-2 border-b flex items-center justify-between text-xs"
        style={{ borderColor: "var(--color-border)" }}
      >
        <span className="font-semibold">
          Draft workflow ({draft.nodes.length} steps)
        </span>
        <Legend />
      </div>
      <div
        className="overflow-auto"
        style={{ background: "var(--color-bg)", maxHeight: 480 }}
      >
        <svg
          width={Math.max(scaledW, size.w || 0)}
          height={Math.max(scaledH, 240)}
          viewBox={`0 0 ${layout.svgW} ${layout.svgH}`}
          preserveAspectRatio="xMidYMin meet"
          style={{ display: "block" }}
        >
          <defs>
            <marker
              id="draft-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill="var(--color-border-hover)" />
            </marker>
            <marker
              id="draft-arrow-danger"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill="var(--color-danger)" />
            </marker>
          </defs>

          {/* Edges */}
          {draft.edges.map((edge, idx) => {
            const from = posMap.get(edge.source);
            const to = posMap.get(edge.target);
            if (!from || !to) return null;
            const inCycle =
              cycleNodeIds.has(edge.source) && cycleNodeIds.has(edge.target);
            return (
              <DraftEdge
                key={`e-${idx}`}
                from={from}
                to={to}
                label={edge.label}
                isCycle={inCycle}
              />
            );
          })}

          {/* Branch pointers that target unknown nodes — drawn as
              dangling red arrows so the user sees the broken link. */}
          {draft.nodes.map((n) => {
            const from = posMap.get(n.id);
            if (!from) return null;
            const broken: { side: "true" | "false"; target: string }[] = [];
            if (n.true_next && !validNodeIds.has(n.true_next)) {
              broken.push({ side: "true", target: n.true_next });
            }
            if (n.false_next && !validNodeIds.has(n.false_next)) {
              broken.push({ side: "false", target: n.false_next });
            }
            return broken.map((b, i) => (
              <DanglingBranch key={`b-${n.id}-${i}`} from={from} side={b.side} />
            ));
          })}

          {/* Nodes */}
          {layout.positioned.map((ln) => {
            const nodeIssues = issuesByNode.get(ln.id) ?? [];
            const hasError = nodeIssues.some((i) => i.severity === "error");
            const hasWarning = nodeIssues.some((i) => i.severity === "warning");
            const isUnreachable = unreachableNodeIds.has(ln.id);
            return (
              <DraftNode
                key={ln.id}
                ln={ln}
                selected={selectedNodeId === ln.id}
                hasError={hasError}
                hasWarning={hasWarning}
                isUnreachable={isUnreachable}
                onClick={() =>
                  onSelectNode(selectedNodeId === ln.id ? null : ln.id)
                }
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ── Subcomponents ──────────────────────────────────────────────────


function DraftEdge({
  from,
  to,
  label,
  isCycle,
}: {
  from: LayoutNode;
  to: LayoutNode;
  label: string;
  isCycle: boolean;
}) {
  const { sx, sy, tx, ty } = edgeAnchors(from, to, "TB");
  const midY = (sy + ty) / 2;
  const d = `M${sx},${sy} C${sx},${midY} ${tx},${midY} ${tx},${ty}`;
  const stroke = isCycle ? "var(--color-danger)" : "var(--color-border-hover)";
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={isCycle ? 2 : 1.5}
        strokeDasharray={isCycle ? "5,3" : undefined}
        markerEnd={
          isCycle ? "url(#draft-arrow-danger)" : "url(#draft-arrow)"
        }
      />
      {label && (
        <text
          x={(sx + tx) / 2}
          y={midY - 6}
          textAnchor="middle"
          fontSize={10}
          fill="var(--color-text-muted)"
        >
          {label}
        </text>
      )}
    </g>
  );
}


function DanglingBranch({
  from,
  side,
}: {
  from: LayoutNode;
  side: "true" | "false";
}) {
  const sx = from.x + NODE_W / 2;
  const sy = from.y + NODE_H;
  const offset = side === "true" ? -40 : 40;
  const tx = sx + offset;
  const ty = sy + 60;
  return (
    <g>
      <path
        d={`M${sx},${sy} L${tx},${ty}`}
        stroke="var(--color-danger)"
        strokeWidth={1.5}
        strokeDasharray="3,3"
        fill="none"
        markerEnd="url(#draft-arrow-danger)"
      />
      <circle cx={tx} cy={ty + 8} r={9} fill="var(--color-danger)" />
      <text
        x={tx}
        y={ty + 12}
        textAnchor="middle"
        fontSize={11}
        fontWeight={700}
        fill="white"
      >
        ?
      </text>
      <text
        x={tx}
        y={ty + 30}
        textAnchor="middle"
        fontSize={9}
        fill="var(--color-danger)"
      >
        {side} branch
      </text>
    </g>
  );
}


function DraftNode({
  ln,
  selected,
  hasError,
  hasWarning,
  isUnreachable,
  onClick,
}: {
  ln: LayoutNode;
  selected: boolean;
  hasError: boolean;
  hasWarning: boolean;
  isUnreachable: boolean;
  onClick: () => void;
}) {
  const colors = NODE_COLORS[ln.node.type] ?? NODE_COLORS.ACTION;
  const label = ln.node.metadata.label || ln.id;

  let ringColor = colors.stroke;
  let ringWidth = selected ? 2.5 : 1.25;
  if (hasError) {
    ringColor = "var(--color-danger)";
    ringWidth = 2.5;
  } else if (hasWarning) {
    ringColor = "var(--color-warning, #b45309)";
    ringWidth = 2;
  }
  const opacity = isUnreachable ? 0.45 : 1;

  return (
    <g
      onClick={onClick}
      style={{ cursor: "pointer", opacity }}
    >
      <rect
        x={ln.x}
        y={ln.y}
        width={NODE_W}
        height={NODE_H}
        rx={10}
        ry={10}
        fill={colors.fill}
        stroke={ringColor}
        strokeWidth={ringWidth}
      />
      <text
        x={ln.x + NODE_W / 2}
        y={ln.y + 20}
        textAnchor="middle"
        fontSize={12}
        fontWeight={600}
        fill={hasError ? "var(--color-danger)" : colors.text}
      >
        {label.length > 22 ? label.slice(0, 20) + "…" : label}
      </text>
      <text
        x={ln.x + NODE_W / 2}
        y={ln.y + 38}
        textAnchor="middle"
        fontSize={9}
        fill="var(--color-text-muted)"
        fontFamily="monospace"
      >
        {ln.node.type}
      </text>
      {isUnreachable && (
        <line
          x1={ln.x + 8}
          y1={ln.y + NODE_H / 2}
          x2={ln.x + NODE_W - 8}
          y2={ln.y + NODE_H / 2}
          stroke="var(--color-text-muted)"
          strokeWidth={1}
          strokeDasharray="2,2"
        />
      )}
    </g>
  );
}


function Legend() {
  return (
    <div className="flex items-center gap-3 text-[10px] text-[var(--color-text-muted)]">
      <span className="flex items-center gap-1">
        <span
          className="inline-block w-2 h-2 rounded-full"
          style={{ background: "var(--color-danger)" }}
        />
        error
      </span>
      <span className="flex items-center gap-1">
        <span
          className="inline-block w-2 h-2 rounded-full"
          style={{ background: "var(--color-warning, #b45309)" }}
        />
        warning
      </span>
      <span className="flex items-center gap-1">
        <span
          className="inline-block w-3 h-0.5"
          style={{
            background: "var(--color-danger)",
            backgroundImage:
              "repeating-linear-gradient(to right, var(--color-danger) 0 4px, transparent 4px 7px)",
          }}
        />
        cycle
      </span>
    </div>
  );
}
