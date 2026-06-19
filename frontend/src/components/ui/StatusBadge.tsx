import { cn, STATUS_COLORS } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  dot?: boolean;
  size?: "sm" | "md";
}

const RUNNING_STATUSES = ["SOURCING", "SCREENING", "PROCESSING", "running"];

export function StatusBadge({ status, dot = true, size = "sm" }: StatusBadgeProps) {
  const colorClass = STATUS_COLORS[status] ?? "text-text-muted border-border bg-card";
  const isRunning = RUNNING_STATUSES.includes(status);

  return (
    <span className={cn(
      "badge border",
      colorClass,
      size === "md" ? "text-xs px-2.5 py-1" : "text-[10px] px-2 py-0.5"
    )}>
      {dot && (
        <span className={cn(
          "inline-block w-1.5 h-1.5 rounded-full flex-shrink-0",
          isRunning ? "animate-pulse" : "",
          status === "OPEN"        ? "bg-primary" :
          status === "SOURCING"    ? "bg-blue-400" :
          status === "SCREENING"   ? "bg-warning" :
          status === "PROCESSING"  ? "bg-amber-400" :
          status === "SHORTLISTED" ? "bg-violet-400" :
          status === "CLOSED"      ? "bg-text-muted" :
          status === "SELECTED"    ? "bg-success" :
          status === "REJECTED"    ? "bg-error" :
          status === "SOURCED"     ? "bg-blue-400" :
          status === "NORMALIZED"  ? "bg-cyan-400" :
          status === "SCREENED"    ? "bg-warning" :
          status === "healthy"     ? "bg-success" :
          status === "degraded"    ? "bg-warning" :
          status === "down"        ? "bg-error" :
          "bg-text-muted"
        )} />
      )}
      {status}
    </span>
  );
}