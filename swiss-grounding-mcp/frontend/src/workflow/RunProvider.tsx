import { createContext, useCallback, useContext, useMemo, useReducer, type ReactNode } from "react";
import type { ExecutionEvent } from "../lib/types";
import { emptyRunState, markRunDisconnected, runReducer, type RunState } from "./runState";

interface RunContextValue {
  state: RunState;
  acceptEvent: (event: ExecutionEvent) => void;
  markDisconnected: () => void;
}

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(runReducer, emptyRunState);
  const acceptEvent = useCallback((event: ExecutionEvent) => dispatch(event), []);
  const markDisconnected = useCallback(() => dispatch({ type: "connection_interrupted" }), []);
  const value = useMemo(() => ({
    state,
    acceptEvent,
    markDisconnected,
  }), [state, acceptEvent, markDisconnected]);

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun(): RunContextValue {
  const context = useContext(RunContext);
  if (!context) throw new Error("useRun must be used within RunProvider");
  return context;
}

export { markRunDisconnected };
