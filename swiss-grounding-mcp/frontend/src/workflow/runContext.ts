import { createContext, useContext } from "react";
import type { ExecutionEvent } from "../lib/types";
import type { RunState } from "./runState";

export interface RunContextValue {
  state: RunState;
  acceptEvent: (event: ExecutionEvent) => void;
  markDisconnected: () => void;
}

export const RunContext = createContext<RunContextValue | null>(null);

export function useRun(): RunContextValue {
  const context = useContext(RunContext);
  if (!context) throw new Error("useRun must be used within RunProvider");
  return context;
}
