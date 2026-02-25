import { useEffect, useState, useMemo } from "react";
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
const LAYER_GAP_Y = 100;
const COL_GAP_X = 220;
const PAD_X = 60;
const PAD_Y = 40;

// ── Topological layered layout ──

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  node: AOPNode;
}

function layoutDAG(nodes: AOPNode[], edges: AOPEdge[]) {
  // Build adjacency + in-degree
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

  // Kahn's algorithm → assign layers
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

  // Group nodes by layer
  const layers = new Map<number, string[]>();
  for (const n of nodes) {
    const l = layer.get(n.id) ?? 0;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)!.push(n.id);
  }

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const positioned: LayoutNode[] = [];

  const maxLayerWidth = Math.max(...[...layers.values()].map((l) => l.length));

  for (const [layerIdx, ids] of layers) {
    const totalWidth = ids.length * COL_GAP_X;
    const startX = (maxLayerWidth * COL_GAP_X - totalWidth) / 2 + PAD_X;
    ids.forEach((id, col) => {
      positioned.push({
        id,
        x: startX + col * COL_GAP_X,
        y: PAD_Y + layerIdx * LAYER_GAP_Y,
        node: nodeMap.get(id)!,
      });
    });
  }

  const maxLayer = Math.max(...layers.keys(), 0);
  const svgW = Math.max(maxLayerWidth * COL_GAP_X + PAD_X * 2, 400);
  const svgH = (maxLayer + 1) * LAYER_GAP_Y + PAD_Y * 2;

  return { positioned, svgW, svgH };
}

// ── Edge path with arrowhead ──

function EdgePath({
  sx, sy, tx, ty, label,
}: {
  sx: number; sy: number; tx: number; ty: number; label: string;
}) {
  const midY = (sy + ty) / 2;
  const d = `M${sx},${sy} C${sx},${midY} ${tx},${midY} ${tx},${ty}`;
  return (
    <g>
      <path d={d} fill="none" stroke="var(--color-border-hover)" strokeWidth={1.5} markerEnd="url(#arrow)" />
      {label && (
        <text
          x={(sx + tx) / 2}
          y={midY - 6}
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
}: {
  ln: LayoutNode;
  selected: boolean;
  onClick: () => void;
}) {
  const colors = NODE_COLORS[ln.node.type] ?? NODE_COLORS.ACTION;
  const label = ln.node.metadata.label || ln.id;
  const typeLabel = ln.node.type;

  return (
    <g
      onClick={onClick}
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

  const layout = useMemo(() => {
    if (!aop) return null;
    return layoutDAG(aop.nodes, aop.edges);
  }, [aop]);

  const posMap = useMemo(() => {
    if (!layout) return new Map<string, LayoutNode>();
    return new Map(layout.positioned.map((ln) => [ln.id, ln]));
  }, [layout]);

  const activeNode = aop?.nodes.find((n) => n.id === selectedNode) ?? null;

  return (
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

        {/* Legend */}
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

      {/* Right — SVG canvas */}
      <div className="lg:col-span-3">
        <div className="card min-h-[300px] flex items-center justify-center overflow-auto">
          {loading && (
            <p className="text-sm text-[var(--color-text-muted)]">Loading graph...</p>
          )}
          {error && (
            <p className="text-sm text-[var(--color-danger)]">{error}</p>
          )}
          {!selectedModule && !loading && (
            <p className="text-subtle text-center">Select a module to view its workflow graph.</p>
          )}
          {layout && aop && (
            <svg
              width={layout.svgW}
              height={layout.svgH}
              viewBox={`0 0 ${layout.svgW} ${layout.svgH}`}
              className="block"
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

              {/* Edges */}
              {aop.edges.map((e) => {
                const src = posMap.get(e.source);
                const tgt = posMap.get(e.target);
                if (!src || !tgt) return null;
                return (
                  <EdgePath
                    key={`${e.source}-${e.target}`}
                    sx={src.x + NODE_W / 2}
                    sy={src.y + NODE_H}
                    tx={tgt.x + NODE_W / 2}
                    ty={tgt.y}
                    label={e.label}
                  />
                );
              })}

              {/* Nodes */}
              {layout.positioned.map((ln) => (
                <NodeRect
                  key={ln.id}
                  ln={ln}
                  selected={selectedNode === ln.id}
                  onClick={() => setSelectedNode(selectedNode === ln.id ? null : ln.id)}
                />
              ))}
            </svg>
          )}
        </div>
      </div>
    </div>
  );
}
