import { useCallback, useMemo, useReducer, type ReactNode } from "react";
import type { ExecutionEvent } from "../lib/types";
import { RunContext } from "./runContext";
import { emptyRunState, runReducer } from "./runState";

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
