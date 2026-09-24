import type { Turn } from "../App";
import { StatusBanner } from "./widgets/StatusBanner";
import { DISPLAYABLE_STATUSES, WIDGET_COMPONENTS, WIDGET_TYPE_BY_TOOL } from "../lib/widgetRegistry";

interface AssistantTurnProps {
  turn: Turn;
  onClarify: (value: string) => void;
}

export function AssistantTurn({ turn, onClarify }: AssistantTurnProps) {
  return (
    <div className="space-y-3">
      {turn.text && <p className="text-neutral-700">{turn.text}</p>}
      {turn.widgets.map((widget, index) => {
        const widgetType = widget.tool ? WIDGET_TYPE_BY_TOOL[widget.tool] : undefined;
        const displayable = widgetType ? DISPLAYABLE_STATUSES[widgetType].includes(widget.status) : false;

        if (!widgetType || !displayable) {
          return (
            <StatusBanner
              key={index}
              status={widget.status}
              message={(widget.data as { message?: string | null }).message ?? null}
              candidates={(widget.data as { candidates?: any[] }).candidates ?? []}
              onClarify={onClarify}
            />
          );
        }

        const Component = WIDGET_COMPONENTS[widgetType];
        return (
          <div key={index} data-testid={`widget-${widget.tool ?? "unknown"}`}>
            <Component data={widget.data} onSelect={() => {}} onSelectConnection={() => {}} />
          </div>
        );
      })}
    </div>
  );
}
