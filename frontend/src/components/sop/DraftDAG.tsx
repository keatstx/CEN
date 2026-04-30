import { useEffect, useMemo, useRef, useState } from "react";
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

const CANVAS_HEIGHT = 480;
const ZOOM_MIN = 0.2;
const ZOOM_MAX = 3;

/**
 * Visual representation of an SOP draft with issue overlays.
 *
 * Pan/zoom controls (mouse wheel, drag, +/-/Fit/1:1 buttons). When a
 * node is selected (either by clicking it on the DAG or by clicking
 * an issue in the ValidationPanel), the canvas auto-pans to bring it
 * to center.
 *
 * Overlay rules:
 * - Red ring on nodes with errors, yellow on warnings, gray opacity +
 *   strikethrough on unreachable.
 * - Cycle edges drawn dashed-red.
 * - Branches pointing at unknown ids drawn as dangling red arrows
 *   ending in a "?" terminal.
 */
export default function DraftDAG({
  draft,
  issues,
  selectedNodeId,
  onSelectNode,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: CANVAS_HEIGHT });
  const [zoom, setZoom] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const dragging = useRef<{
    x: number;
    y: number;
    tx: number;
    ty: number;
  } | null>(null);

  // Track container width via ResizeObserver so the SVG fills the
  // available space and the fit-to-screen math is correct.
  useEffect(() => {
    const c = containerRef.current;
    if (!c || typeof ResizeObserver === "undefined") return;
    const update = () =>
      setSize({ w: c.clientWidth, h: c.clientHeight || CANVAS_HEIGHT });
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

  // Issue lookups.
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

  // Fit-to-screen — compute zoom + center so the whole layout fits
  // the canvas. Stable and predictable.
  const fit = () => {
    if (size.w <= 0) return;
    const z = Math.min(size.w / layout.svgW, CANVAS_HEIGHT / layout.svgH, 1);
    setZoom(z);
    setTx((size.w - layout.svgW * z) / 2);
    setTy((CANVAS_HEIGHT - layout.svgH * z) / 2);
  };

  // Run fit() on first render and whenever the draft / canvas width
  // changes. This is the "land in a sensible state" behavior.
  useEffect(() => {
    fit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout, size.w]);

  // Auto-pan when the selected node changes — center it in the
  // visible canvas. The user clicked an issue or a node and expects
  // the highlight to be visible without manual scrolling.
  useEffect(() => {
    if (!selectedNodeId || size.w <= 0) return;
    const ln = posMap.get(selectedNodeId);
    if (!ln) return;
    const targetX = size.w / 2 - (ln.x + NODE_W / 2) * zoom;
    const targetY = CANVAS_HEIGHT / 2 - (ln.y + NODE_H / 2) * zoom;
    setTx(targetX);
    setTy(targetY);
    // Don't include `zoom` as a dep — would trigger every wheel event.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId]);

  // Pan/zoom handlers — wheel zooms anchored on the cursor; drag pans.
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const c = containerRef.current;
    if (!c) return;
    const rect = c.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    const newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom * factor));
    const wx = (mx - tx) / zoom;
    const wy = (my - ty) / zoom;
    setZoom(newZoom);
    setTx(mx - wx * newZoom);
    setTy(my - wy * newZoom);
  };

  const onMouseDown = (e: React.MouseEvent) => {
    // Don't start a drag when the user clicks a node — let that
    // event fire (the node's onClick is on the <g> element).
    if ((e.target as Element).closest("g[data-node]")) return;
    dragging.current = { x: e.clientX, y: e.clientY, tx, ty };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging.current) return;
    setTx(dragging.current.tx + (e.clientX - dragging.current.x));
    setTy(dragging.current.ty + (e.clientY - dragging.current.y));
  };
  const onMouseUp = () => {
    dragging.current = null;
  };

  return (
    <div
      className="card overflow-hidden p-0"
      style={{ height: CANVAS_HEIGHT + 38 }}
    >
      <div
        className="px-3 py-2 border-b flex items-center justify-between text-xs"
        style={{ borderColor: "var(--color-border)" }}
      >
        <span className="font-semibold">
          Draft workflow ({draft.nodes.length} steps)
        </span>
        <div className="flex items-center gap-3">
          <Legend />
          <ZoomControls
            zoom={zoom}
            onZoomIn={() => setZoom((z) => Math.min(ZOOM_MAX, z * 1.2))}
            onZoomOut={() => setZoom((z) => Math.max(ZOOM_MIN, z / 1.2))}
            onFit={fit}
            onReset={() => {
              setZoom(1);
              setTx(0);
              setTy(0);
            }}
          />
        </div>
      </div>
      <div
        ref={containerRef}
        className="relative"
        style={{
          height: CANVAS_HEIGHT,
          background: "var(--color-bg)",
          cursor: dragging.current ? "grabbing" : "grab",
          userSelect: "none",
        }}
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <svg
          width={size.w || 800}
          height={CANVAS_HEIGHT}
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

          <g transform={`translate(${tx},${ty}) scale(${zoom})`}>
            {/* Edges */}
            {draft.edges.map((edge, idx) => {
              const from = posMap.get(edge.source);
              const to = posMap.get(edge.target);
              if (!from || !to) return null;
              const inCycle =
                cycleNodeIds.has(edge.source) &&
                cycleNodeIds.has(edge.target);
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

            {/* Dangling branches */}
            {draft.nodes.map((n) => {
              const from = posMap.get(n.id);
              if (!from) return null;
              const broken: { side: "true" | "false" }[] = [];
              if (n.true_next && !validNodeIds.has(n.true_next)) {
                broken.push({ side: "true" });
              }
              if (n.false_next && !validNodeIds.has(n.false_next)) {
                broken.push({ side: "false" });
              }
              return broken.map((b, i) => (
                <DanglingBranch
                  key={`b-${n.id}-${i}`}
                  from={from}
                  side={b.side}
                />
              ));
            })}

            {/* Nodes */}
            {layout.positioned.map((ln) => {
              const nodeIssues = issuesByNode.get(ln.id) ?? [];
              const hasError = nodeIssues.some((i) => i.severity === "error");
              const hasWarning = nodeIssues.some(
                (i) => i.severity === "warning",
              );
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
          </g>
        </svg>
      </div>
    </div>
  );
}

// ── Subcomponents ──────────────────────────────────────────────────


function ZoomControls({
  zoom,
  onZoomIn,
  onZoomOut,
  onFit,
  onReset,
}: {
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onReset: () => void;
}) {
  const btn =
    "px-1.5 py-0.5 rounded border hover:bg-[var(--color-bg)] text-[11px]";
  return (
    <div
      className="flex items-center gap-1"
      style={{ borderColor: "var(--color-border)" }}
    >
      <button
        type="button"
        className={btn}
        onClick={onZoomIn}
        title="Zoom in"
        style={{ borderColor: "var(--color-border)" }}
      >
        +
      </button>
      <button
        type="button"
        className={btn}
        onClick={onZoomOut}
        title="Zoom out"
        style={{ borderColor: "var(--color-border)" }}
      >
        −
      </button>
      <button
        type="button"
        className={btn}
        onClick={onFit}
        title="Fit to screen"
        style={{ borderColor: "var(--color-border)" }}
      >
        Fit
      </button>
      <button
        type="button"
        className={btn}
        onClick={onReset}
        title="Reset to 100%"
        style={{ borderColor: "var(--color-border)" }}
      >
        1:1
      </button>
      <span className="text-[10px] font-mono text-[var(--color-text-muted)] w-10 text-right">
        {Math.round(zoom * 100)}%
      </span>
    </div>
  );
}


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
  let ringWidth = selected ? 3 : 1.25;
  if (selected) {
    ringColor = "var(--color-accent)";
    ringWidth = 3.5;
  } else if (hasError) {
    ringColor = "var(--color-danger)";
    ringWidth = 2.5;
  } else if (hasWarning) {
    ringColor = "var(--color-warning, #b45309)";
    ringWidth = 2;
  }
  const opacity = isUnreachable ? 0.45 : 1;

  return (
    <g
      data-node="true"
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
    </div>
  );
}
