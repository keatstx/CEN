import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import type { AOPDefinition, AOPNode, AOPEdge } from "../types";
import { MODULE_CONFIGS } from "../types";
import { fetchModule } from "../api";

// ── Color mapping per node type ──

const NODE_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  ACTION:    { fill: "#2563eb18", stroke: "#2563eb", text: "#2563eb" },
  CONDITION: { fill: "#d9770618", stroke: "#d97706", text: "#d97706" },
  HANDOFF:   { fill: "#05966918", stroke: "#059669", text: "#059669" },
  APPROVAL:  { fill: "#7c3aed18", stroke: "#7c3aed", text: "#7c3aed" },
};

// ── Layout constants ──

const NODE_W = 180;
const NODE_H = 52;
const LAYER_GAP = 100;   // gap between layers (along flow direction)
const COL_GAP = 40;      // gap between siblings (perpendicular to flow)
const PAD = 60;

type Direction = "TB" | "LR";

// ── Topological layered layout ──

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  node: AOPNode;
}

function layoutDAG(nodes: AOPNode[], edges: AOPEdge[], dir: Direction) {
  const adj = new Map<string, string[]>();
  const inDeg = new Map<string, number>();
  for (const n of nodes) {
    adj.set(n.id, []);
    inDeg.set(n.id, 0);
  }
  for (const e of edges) {
    adj.get(e.source)?.push(e.target);
    inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
  }

  const layer = new Map<string, number>();
  const queue: string[] = [];
  for (const n of nodes) {
    if ((inDeg.get(n.id) ?? 0) === 0) queue.push(n.id);
  }
  while (queue.length > 0) {
    const cur = queue.shift()!;
    const curLayer = layer.get(cur) ?? 0;
    for (const next of adj.get(cur) ?? []) {
      const nextLayer = Math.max(layer.get(next) ?? 0, curLayer + 1);
      layer.set(next, nextLayer);
      inDeg.set(next, (inDeg.get(next) ?? 0) - 1);
      if (inDeg.get(next) === 0) queue.push(next);
    }
  }

  const layers = new Map<number, string[]>();
  for (const n of nodes) {
    const l = layer.get(n.id) ?? 0;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)!.push(n.id);
  }

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const positioned: LayoutNode[] = [];

  // Per-direction step sizes
  const stepLayer = dir === "TB" ? NODE_H + LAYER_GAP : NODE_W + LAYER_GAP;
  const stepSibling = dir === "TB" ? NODE_W + COL_GAP : NODE_H + COL_GAP;

  const maxLayerCount = Math.max(...[...layers.values()].map((l) => l.length));
  const sectionSize = maxLayerCount * stepSibling;

  for (const [layerIdx, ids] of layers) {
    const total = ids.length * stepSibling;
    const start = (sectionSize - total) / 2 + PAD;
    ids.forEach((id, col) => {
      const along = PAD + layerIdx * stepLayer;
      const across = start + col * stepSibling;
      positioned.push({
        id,
        x: dir === "TB" ? across : along,
        y: dir === "TB" ? along : across,
        node: nodeMap.get(id)!,
      });
    });
  }

  const maxLayer = Math.max(...layers.keys(), 0);
  const alongTotal = (maxLayer + 1) * stepLayer + PAD * 2;
  const acrossTotal = sectionSize + PAD * 2;
  const svgW = dir === "TB" ? acrossTotal : alongTotal;
  const svgH = dir === "TB" ? alongTotal : acrossTotal;

  return { positioned, svgW: Math.max(svgW, 400), svgH: Math.max(svgH, 300) };
}

// ── Edge path with arrowhead ──

function EdgePath({
  sx, sy, tx, ty, label, dir,
}: {
  sx: number; sy: number; tx: number; ty: number; label: string; dir: Direction;
}) {
  let d: string;
  let labelX: number;
  let labelY: number;
  if (dir === "TB") {
    const midY = (sy + ty) / 2;
    d = `M${sx},${sy} C${sx},${midY} ${tx},${midY} ${tx},${ty}`;
    labelX = (sx + tx) / 2;
    labelY = midY - 6;
  } else {
    const midX = (sx + tx) / 2;
    d = `M${sx},${sy} C${midX},${sy} ${midX},${ty} ${tx},${ty}`;
    labelX = midX;
    labelY = (sy + ty) / 2 - 6;
  }
  return (
    <g>
      <path d={d} fill="none" stroke="var(--color-border-hover)" strokeWidth={1.5} markerEnd="url(#arrow)" />
      {label && (
        <text
          x={labelX}
          y={labelY}
          textAnchor="middle"
          fontSize={10}
          fill="var(--color-text-muted)"
          fontFamily="inherit"
        >
          {label}
        </text>
      )}
    </g>
  );
}

// ── Node rectangle ──

function NodeRect({
  ln,
  selected,
  onClick,
  onHover,
  onLeave,
}: {
  ln: LayoutNode;
  selected: boolean;
  onClick: () => void;
  onHover: (id: string, clientX: number, clientY: number) => void;
  onLeave: () => void;
}) {
  const colors = NODE_COLORS[ln.node.type] ?? NODE_COLORS.ACTION;
  const label = ln.node.metadata.label || ln.id;
  const typeLabel = ln.node.type;

  return (
    <g
      onClick={onClick}
      onMouseEnter={(e) => onHover(ln.id, e.clientX, e.clientY)}
      onMouseMove={(e) => onHover(ln.id, e.clientX, e.clientY)}
      onMouseLeave={onLeave}
      style={{ cursor: "pointer" }}
    >
      <rect
        x={ln.x}
        y={ln.y}
        width={NODE_W}
        height={NODE_H}
        rx={10}
        ry={10}
        fill={colors.fill}
        stroke={selected ? colors.stroke : colors.stroke + "80"}
        strokeWidth={selected ? 2 : 1.25}
      />
      <text
        x={ln.x + NODE_W / 2}
        y={ln.y + 20}
        textAnchor="middle"
        fontSize={12}
        fontWeight={600}
        fill={colors.text}
        fontFamily="inherit"
      >
        {label.length > 22 ? label.slice(0, 20) + "..." : label}
      </text>
      <text
        x={ln.x + NODE_W / 2}
        y={ln.y + 38}
        textAnchor="middle"
        fontSize={9}
        fill="var(--color-text-muted)"
        fontFamily="monospace"
      >
        {typeLabel}
      </text>
    </g>
  );
}

// ── Detail panel ──

function DetailPanel({ node }: { node: AOPNode }) {
  const colors = NODE_COLORS[node.type] ?? NODE_COLORS.ACTION;
  return (
    <div className="card animate-fade-in space-y-3">
      <div className="flex items-center gap-2">
        <span
          className="inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: colors.stroke }}
        />
        <h3 className="text-sm font-semibold">{node.metadata.label || node.id}</h3>
        <span className="text-[10px] font-mono text-[var(--color-text-muted)]">{node.type}</span>
      </div>

      <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
        {node.metadata.description || "No description."}
      </p>

      {node.type === "CONDITION" && (
        <div className="text-xs space-y-1">
          <p className="font-medium text-[var(--color-text-muted)]">Condition</p>
          <code className="block bg-[var(--color-surface)] px-2 py-1 rounded text-[11px]">
            {node.condition_field} {node.condition_operator} {String(node.condition_value)}
          </code>
          <p className="text-[var(--color-text-muted)]">
            True → <span className="font-mono">{node.true_next}</span>
            {" · "}
            False → <span className="font-mono">{node.false_next}</span>
          </p>
        </div>
      )}

      {Object.keys(node.metadata.params).length > 0 && (
        <div className="text-xs space-y-1">
          <p className="font-medium text-[var(--color-text-muted)]">Parameters</p>
          <pre className="bg-[var(--color-surface)] px-2 py-1.5 rounded text-[11px] overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(node.metadata.params, null, 2)}
          </pre>
        </div>
      )}

      <p className="text-[10px] font-mono text-[var(--color-text-muted)]">ID: {node.id}</p>
    </div>
  );
}

// ── Pan/Zoom canvas ──

interface CanvasProps {
  aop: AOPDefinition;
  layout: ReturnType<typeof layoutDAG>;
  posMap: Map<string, LayoutNode>;
  selectedNode: string | null;
  setSelectedNode: (id: string | null) => void;
  dir: Direction;
  className?: string;
}

function DAGCanvas({
  aop, layout, posMap, selectedNode, setSelectedNode, dir, className,
}: CanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const dragging = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  const onHoverNode = useCallback((id: string, clientX: number, clientY: number) => {
    const c = containerRef.current;
    if (!c) return;
    const rect = c.getBoundingClientRect();
    setHover({ id, x: clientX - rect.left, y: clientY - rect.top });
  }, []);
  const onLeaveNode = useCallback(() => setHover(null), []);

  const hoverNode = hover ? aop.nodes.find((n) => n.id === hover.id) ?? null : null;

  const fit = useCallback(() => {
    const c = containerRef.current;
    if (!c) return;
    const cw = c.clientWidth;
    const ch = c.clientHeight;
    if (cw <= 0 || ch <= 0) return;
    const z = Math.min(cw / layout.svgW, ch / layout.svgH, 1);
    setZoom(z);
    setTx((cw - layout.svgW * z) / 2);
    setTy((ch - layout.svgH * z) / 2);
  }, [layout.svgW, layout.svgH]);

  useEffect(() => {
    fit();
  }, [fit]);

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const c = containerRef.current;
    if (!c) return;
    const rect = c.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    const newZoom = Math.max(0.1, Math.min(4, zoom * factor));
    // Keep mouse anchor stable
    const wx = (mx - tx) / zoom;
    const wy = (my - ty) / zoom;
    setZoom(newZoom);
    setTx(mx - wx * newZoom);
    setTy(my - wy * newZoom);
  };

  const onMouseDown = (e: React.MouseEvent) => {
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
    <div className={`relative ${className ?? ""}`}>
      {/* Toolbar */}
      <div className="absolute top-2 right-2 z-10 flex gap-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md p-1 shadow-sm">
        <button
          className="px-2 py-1 text-xs hover:bg-[var(--color-bg)] rounded"
          onClick={() => setZoom((z) => Math.min(4, z * 1.2))}
          title="Zoom in"
        >+</button>
        <button
          className="px-2 py-1 text-xs hover:bg-[var(--color-bg)] rounded"
          onClick={() => setZoom((z) => Math.max(0.1, z / 1.2))}
          title="Zoom out"
        >−</button>
        <button
          className="px-2 py-1 text-xs hover:bg-[var(--color-bg)] rounded"
          onClick={fit}
          title="Fit to screen"
        >Fit</button>
        <button
          className="px-2 py-1 text-xs hover:bg-[var(--color-bg)] rounded"
          onClick={() => { setZoom(1); setTx(0); setTy(0); }}
          title="100%"
        >1:1</button>
        <span className="px-1 text-[10px] text-[var(--color-text-muted)] self-center font-mono">
          {Math.round(zoom * 100)}%
        </span>
      </div>

      <div
        ref={containerRef}
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        className="w-full h-full overflow-hidden cursor-grab active:cursor-grabbing"
        style={{ touchAction: "none" }}
      >
        <svg
          width={layout.svgW}
          height={layout.svgH}
          viewBox={`0 0 ${layout.svgW} ${layout.svgH}`}
          style={{
            transform: `translate(${tx}px, ${ty}px) scale(${zoom})`,
            transformOrigin: "0 0",
            display: "block",
          }}
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX={9}
              refY={5}
              markerWidth={7}
              markerHeight={7}
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-border-hover)" />
            </marker>
          </defs>

          {aop.edges.map((e) => {
            const src = posMap.get(e.source);
            const tgt = posMap.get(e.target);
            if (!src || !tgt) return null;
            const sx = dir === "TB" ? src.x + NODE_W / 2 : src.x + NODE_W;
            const sy = dir === "TB" ? src.y + NODE_H : src.y + NODE_H / 2;
            const tx2 = dir === "TB" ? tgt.x + NODE_W / 2 : tgt.x;
            const ty2 = dir === "TB" ? tgt.y : tgt.y + NODE_H / 2;
            return (
              <EdgePath
                key={`${e.source}-${e.target}`}
                sx={sx}
                sy={sy}
                tx={tx2}
                ty={ty2}
                label={e.label}
                dir={dir}
              />
            );
          })}

          {layout.positioned.map((ln) => (
            <g key={ln.id} data-node>
              <NodeRect
                ln={ln}
                selected={selectedNode === ln.id}
                onClick={() => setSelectedNode(selectedNode === ln.id ? null : ln.id)}
                onHover={onHoverNode}
                onLeave={onLeaveNode}
              />
            </g>
          ))}
        </svg>
      </div>

      {/* Hover tooltip */}
      {hover && hoverNode && (
        <div
          className="pointer-events-none absolute z-20 max-w-xs rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 shadow-lg text-xs"
          style={{
            left: Math.min(hover.x + 14, (containerRef.current?.clientWidth ?? 0) - 320),
            top: Math.min(hover.y + 14, (containerRef.current?.clientHeight ?? 0) - 140),
          }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: (NODE_COLORS[hoverNode.type] ?? NODE_COLORS.ACTION).stroke }}
            />
            <span className="font-semibold text-[var(--color-text-primary)]">
              {hoverNode.metadata.label || hoverNode.id}
            </span>
            <span className="text-[10px] font-mono text-[var(--color-text-muted)] ml-auto">
              {hoverNode.type}
            </span>
          </div>
          {hoverNode.metadata.description && (
            <p className="text-[var(--color-text-secondary)] leading-relaxed">
              {hoverNode.metadata.description}
            </p>
          )}
          <p className="mt-1 text-[10px] font-mono text-[var(--color-text-muted)]">
            {hoverNode.id}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main component ──

interface Props {
  modules: string[];
  selectedModule: string;
  onModuleChange: (mod: string) => void;
}

export default function DAGViewer({ modules, selectedModule, onModuleChange }: Props) {
  const [aop, setAop] = useState<AOPDefinition | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [dir, setDir] = useState<Direction>("TB");
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    if (!selectedModule) {
      setAop(null);
      setSelectedNode(null);
      return;
    }
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    fetchModule(selectedModule)
      .then(setAop)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedModule]);

  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  const layout = useMemo(() => {
    if (!aop) return null;
    return layoutDAG(aop.nodes, aop.edges, dir);
  }, [aop, dir]);

  const posMap = useMemo(() => {
    if (!layout) return new Map<string, LayoutNode>();
    return new Map(layout.positioned.map((ln) => [ln.id, ln]));
  }, [layout]);

  const activeNode = aop?.nodes.find((n) => n.id === selectedNode) ?? null;

  const toolbar = (
    <div className="flex items-center gap-2">
      <div className="flex border border-[var(--color-border)] rounded-md overflow-hidden">
        <button
          className={`px-2 py-1 text-xs ${dir === "TB" ? "bg-[var(--color-bg)] font-semibold" : ""}`}
          onClick={() => setDir("TB")}
          title="Top to bottom"
        >↓ TB</button>
        <button
          className={`px-2 py-1 text-xs ${dir === "LR" ? "bg-[var(--color-bg)] font-semibold" : ""}`}
          onClick={() => setDir("LR")}
          title="Left to right"
        >→ LR</button>
      </div>
      <button
        className="px-2 py-1 text-xs border border-[var(--color-border)] rounded-md hover:bg-[var(--color-bg)]"
        onClick={() => setFullscreen((f) => !f)}
        title={fullscreen ? "Exit fullscreen (Esc)" : "Fullscreen"}
      >{fullscreen ? "Exit ⛶" : "⛶ Fullscreen"}</button>
    </div>
  );

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Left — module selector + detail */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card">
            <div className="space-y-3">
              <label
                htmlFor="dag-module-select"
                className="block text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)]"
              >
                Module
              </label>
              <select
                id="dag-module-select"
                value={selectedModule}
                onChange={(e) => onModuleChange(e.target.value)}
              >
                <option value="">— Choose a module —</option>
                {modules.map((m) => (
                  <option key={m} value={m}>
                    {MODULE_CONFIGS[m]?.label ?? m}
                  </option>
                ))}
              </select>
              {aop && (
                <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">
                  {aop.description || MODULE_CONFIGS[selectedModule]?.description}
                </p>
              )}
            </div>
          </div>

          {aop && (
            <div className="card">
              <div className="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
                <span>{aop.nodes.length} nodes</span>
                <span>{aop.edges.length} edges</span>
                <span>v{aop.version}</span>
              </div>
            </div>
          )}

          {aop && (
            <div className="card space-y-2">
              <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">Legend</p>
              <div className="flex flex-wrap gap-3">
                {Object.entries(NODE_COLORS).map(([type, c]) => (
                  <div key={type} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: c.stroke }} />
                    <span className="text-[11px] text-[var(--color-text-secondary)]">{type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeNode && <DetailPanel node={activeNode} />}
        </div>

        {/* Right — canvas */}
        <div className="lg:col-span-3">
          <div className="card p-2">
            {aop && (
              <div className="flex items-center justify-between px-2 py-1 mb-1">
                <span className="text-[11px] text-[var(--color-text-muted)]">
                  Drag to pan · Scroll to zoom
                </span>
                {toolbar}
              </div>
            )}
            <div className="h-[600px] flex items-center justify-center bg-[var(--color-bg)] rounded">
              {loading && <p className="text-sm text-[var(--color-text-muted)]">Loading graph...</p>}
              {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
              {!selectedModule && !loading && (
                <p className="text-subtle text-center">Select a module to view its workflow graph.</p>
              )}
              {layout && aop && !fullscreen && (
                <DAGCanvas
                  aop={aop}
                  layout={layout}
                  posMap={posMap}
                  selectedNode={selectedNode}
                  setSelectedNode={setSelectedNode}
                  dir={dir}
                  className="w-full h-full"
                />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Fullscreen overlay */}
      {fullscreen && layout && aop && (
        <div className="fixed inset-0 z-50 bg-[var(--color-bg)] flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)]">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold">
                {MODULE_CONFIGS[selectedModule]?.label ?? selectedModule}
              </h2>
              <span className="text-xs text-[var(--color-text-muted)]">
                {aop.nodes.length} nodes · {aop.edges.length} edges · Drag to pan · Scroll to zoom · Esc to exit
              </span>
            </div>
            {toolbar}
          </div>
          <div className="flex-1 relative">
            <DAGCanvas
              aop={aop}
              layout={layout}
              posMap={posMap}
              selectedNode={selectedNode}
              setSelectedNode={setSelectedNode}
              dir={dir}
              className="absolute inset-0"
            />
          </div>
        </div>
      )}
    </>
  );
}
