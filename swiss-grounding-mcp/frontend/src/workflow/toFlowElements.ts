import type { Edge, Node } from "@xyflow/react";
import type { RunNode, RunState } from "./runState";

export type ExecutionNodeData = RunNode & { children: RunNode[]; [key: string]: unknown };

interface RoundGroup {
  parent: RunNode;
  children: RunNode[];
}

const COLUMN_WIDTH = 300;
const ROW_Y = 60;

function groupByRound(state: RunState): RoundGroup[] {
  const groups: RoundGroup[] = [];
  let current: RoundGroup | null = null;
  for (const id of state.nodeOrder) {
    const node = state.nodes[id];
    if (!node) continue;
    if (id.startsWith("model-")) {
      current = { parent: node, children: [] };
      groups.push(current);
    } else if (current) {
      current.children.push(node);
    } else {
      groups.push({ parent: node, children: [] });
    }
  }
  return groups;
}

export function toFlowElements(state: RunState): { nodes: Node<ExecutionNodeData>[]; edges: Edge[] } {
  const groups = groupByRound(state);
  const nodes = groups.map((group, index) => ({
    id: group.parent.id,
    type: "execution",
    position: { x: index * COLUMN_WIDTH, y: ROW_Y },
    data: { ...group.parent, children: group.children } as ExecutionNodeData,
    draggable: false,
    connectable: false,
    deletable: false,
  }));
  const edges = groups.slice(1).map((group, index) => ({
    id: `${groups[index].parent.id}-${group.parent.id}`,
    source: groups[index].parent.id,
    target: group.parent.id,
    type: "smoothstep",
    animated: group.parent.status === "running",
    style: { stroke: "#8fbf9d", strokeWidth: 1.5 },
  }));
  return { nodes, edges };
}
