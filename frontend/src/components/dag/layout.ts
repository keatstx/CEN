import type { AOPEdge, AOPNode } from "../../types";

/** Type colors — reused by every DAG renderer in the app. */
export const NODE_COLORS: Record<
  string,
  { fill: string; stroke: string; text: string }
> = {
  ACTION: { fill: "#2563eb18", stroke: "#2563eb", text: "#2563eb" },
  CONDITION: { fill: "#d9770618", stroke: "#d97706", text: "#d97706" },
  HANDOFF: { fill: "#05966918", stroke: "#059669", text: "#059669" },
  APPROVAL: { fill: "#7c3aed18", stroke: "#7c3aed", text: "#7c3aed" },
};

export const NODE_W = 180;
export const NODE_H = 52;
export const LAYER_GAP = 100;
export const COL_GAP = 40;
export const PAD = 60;

export type Direction = "TB" | "LR";

export interface LayoutNode {
  id: string;
  x: number;
  y: number;
  node: AOPNode;
}

/**
 * Topological layered layout.
 *
 * Returns positioned nodes plus the SVG canvas dimensions. Cycles
 * are tolerated — nodes whose in-degree never hits 0 land in layer 0.
 * Used by both the live DAG Viewer (with pan/zoom) and the SOP draft
 * DAG (fit-to-screen).
 */
export function layoutDAG(
  nodes: AOPNode[],
  edges: AOPEdge[],
  dir: Direction,
): { positioned: LayoutNode[]; svgW: number; svgH: number } {
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

/**
 * Compute the source-anchor and target-anchor of an edge between two
 * positioned nodes, given the flow direction. Returns the (x,y) of
 * each end. Used by every edge renderer.
 */
export function edgeAnchors(
  from: LayoutNode,
  to: LayoutNode,
  dir: Direction,
): { sx: number; sy: number; tx: number; ty: number } {
  if (dir === "TB") {
    return {
      sx: from.x + NODE_W / 2,
      sy: from.y + NODE_H,
      tx: to.x + NODE_W / 2,
      ty: to.y,
    };
  }
  return {
    sx: from.x + NODE_W,
    sy: from.y + NODE_H / 2,
    tx: to.x,
    ty: to.y + NODE_H / 2,
  };
}
