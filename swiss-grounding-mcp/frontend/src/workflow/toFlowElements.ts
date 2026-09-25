import type { Edge, Node } from "@xyflow/react";
import type { RunNode, RunState } from "./runState";

export type ExecutionNodeData = RunNode & { [key: string]: unknown };

export function toFlowElements(state: RunState): { nodes: Node<ExecutionNodeData>[]; edges: Edge[] } {
  const nodes = state.nodeOrder.map((id, index) => ({
    id,
    type: "execution",
    position: { x: index * 300, y: index % 2 === 0 ? 70 : 190 },
    data: state.nodes[id] as ExecutionNodeData,
    draggable: false,
    connectable: false,
  }));
  const edges = state.nodeOrder.slice(1).map((id, index) => ({
    id: `${state.nodeOrder[index]}-${id}`,
    source: state.nodeOrder[index],
    target: id,
    type: "smoothstep",
    animated: state.nodes[id].status === "running",
    style: { stroke: "#78b98c", strokeWidth: 1.5 },
  }));
  return { nodes, edges };
}
