import { cn } from "@/lib/utils";

interface ScoreBarProps {
  score: number;
  max?: number;
  showLabel?: boolean;
  size?: "sm" | "md";
}

export function ScoreBar({ score, max = 10, showLabel = true, size = "sm" }: ScoreBarProps) {
  const pct = Math.min((score / max) * 100, 100);
  const tier = pct >= 70 ? "bg-success" : pct >= 50 ? "bg-warning" : "bg-error";

  return (
    <div className="flex items-center gap-2 flex-1">
      <div className={cn("skill-bar-track", size === "md" ? "h-2" : "h-1.5")}>
        <div
          className={cn("skill-bar-fill", tier)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="font-mono text-[10px] text-text-muted w-7 text-right shrink-0">
          {score?.toFixed(1)}
        </span>
      )}
    </div>
  );
}