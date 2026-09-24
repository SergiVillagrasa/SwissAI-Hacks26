import type { Turn } from "../App";
import { StatusBanner } from "./widgets/StatusBanner";
import { NewtonsCradle } from "./NewtonsCradle";
import {
  DISPLAYABLE_STATUSES,
  WIDGET_COMPONENTS,
  WIDGET_GRID_SPAN,
  WIDGET_TYPE_BY_TOOL,
} from "../lib/widgetRegistry";

interface AssistantTurnProps {
  turn: Turn;
  isPending?: boolean;
  onClarify: (value: string) => void;
}

export function AssistantTurn({ turn, isPending = false, onClarify }: AssistantTurnProps) {
  const isWaiting = isPending && !turn.text && turn.widgets.length === 0;

  return (
    <div className="space-y-3">
      {isWaiting && <NewtonsCradle />}
      {turn.text && (
        <p className="max-w-2xl text-[15px] leading-relaxed text-neutral-700">{turn.text}</p>
      )}
      {turn.widgets.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {turn.widgets.map((widget, index) => {
            const widgetType = widget.tool ? WIDGET_TYPE_BY_TOOL[widget.tool] : undefined;
            const displayable = widgetType
              ? DISPLAYABLE_STATUSES[widgetType].includes(widget.status)
              : false;
            const span = widgetType ? WIDGET_GRID_SPAN[widgetType] : "wide";
            const spanClass = span === "wide" ? "md:col-span-2" : "";

            if (!widgetType || !displayable) {
              return (
                <div key={index} className={spanClass}>
                  <StatusBanner
                    status={widget.status}
                    message={(widget.data as { message?: string | null }).message ?? null}
                    candidates={(widget.data as { candidates?: any[] }).candidates ?? []}
                    onClarify={onClarify}
                  />
                </div>
              );
            }

            const Component = WIDGET_COMPONENTS[widgetType];
            return (
              <div key={index} className={spanClass} data-testid={`widget-${widget.tool ?? "unknown"}`}>
                <Component data={widget.data} onSelect={() => {}} onSelectConnection={() => {}} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
