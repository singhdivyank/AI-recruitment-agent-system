import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`;
}

export const STATUS_COLORS: Record<string, string> = {
  OPEN:        "text-primary border-primary/30 bg-primary/10",
  SOURCING:    "text-blue-400 border-blue-400/30 bg-blue-400/10",
  SCREENING:   "text-warning border-warning/30 bg-warning/10",
  SHORTLISTED: "text-violet-400 border-violet-400/30 bg-violet-400/10",
  CLOSED:      "text-text-muted border-border bg-card",
  REJECTED:    "text-error border-error/30 bg-error/10",
  PROCESSING:  "text-amber-400 border-amber-400/30 bg-amber-400/10",
  SOURCED:     "text-blue-400 border-blue-400/30 bg-blue-400/10",
  NORMALIZED:  "text-cyan-400 border-cyan-400/30 bg-cyan-400/10",
  SCREENED:    "text-warning border-warning/30 bg-warning/10",
  SELECTED:    "text-success border-success/30 bg-success/10",
  healthy:     "text-success border-success/30 bg-success/10",
  degraded:    "text-warning border-warning/30 bg-warning/10",
  down:        "text-error border-error/30 bg-error/10",
};

export const PIPELINE_STAGES = ["OPEN","SOURCING","SCREENING","SHORTLISTED","CLOSED"] as const;