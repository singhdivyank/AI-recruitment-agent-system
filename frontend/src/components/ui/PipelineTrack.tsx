import { cn, PIPELINE_STAGES } from "@/lib/utils";

interface PipelineTrackProps {
  status: string;
  compact?: boolean;
}

export function PipelineTrack({ status, compact = true }: PipelineTrackProps) {
  const currentIdx = PIPELINE_STAGES.indexOf(status as typeof PIPELINE_STAGES[number]);
  const failed = status === "REJECTED";

  return (
    <div className="flex items-center gap-0">
      {PIPELINE_STAGES.map((stage, i) => {
        const done   = !failed && currentIdx > i;
        const active = !failed && currentIdx === i;
        const isFail = failed && i === 0;

        return (
          <div key={stage} className="flex items-center">
            <div
              title={stage}
              className={cn(
                "rounded-full transition-all duration-300",
                compact ? "w-1.5 h-1.5" : "w-2 h-2",
                done   ? "bg-primary" :
                active ? "bg-primary shadow-[0_0_0_3px_rgba(99,102,241,0.2)]" :
                isFail ? "bg-error" :
                         "bg-border"
              )}
            />
            {i < PIPELINE_STAGES.length - 1 && (
              <div className={cn(
                "h-px transition-all duration-300",
                compact ? "w-3" : "w-5",
                done ? "bg-primary" : "bg-border"
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}