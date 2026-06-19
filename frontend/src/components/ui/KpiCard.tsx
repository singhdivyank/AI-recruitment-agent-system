import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon?: ReactNode;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  accent?: "primary" | "success" | "warning" | "error";
  mono?: boolean;
}

const ACCENT_MAP = {
  primary: "text-primary",
  success: "text-success",
  warning: "text-warning",
  error:   "text-error",
};

export function KpiCard({
  label, value, sub, icon, trend, trendValue, accent = "primary", mono = true,
}: KpiCardProps) {
  const valueColor = ACCENT_MAP[accent];

  return (
    <div className="metric-card flex flex-col gap-3 animate-slide-up">
      <div className="flex items-start justify-between">
        <span className="section-eyebrow">{label}</span>
        {icon && (
          <span className="text-text-faint">{icon}</span>
        )}
      </div>

      <div className={cn(
        "stat-number",
        valueColor,
        mono ? "font-mono-data" : "font-display"
      )}>
        {value}
      </div>

      {(sub || trend) && (
        <div className="flex items-center gap-2">
          {trend && (
            <span className={cn(
              "flex items-center gap-0.5 text-[10px] font-mono font-medium",
              trend === "up"   ? "text-success" :
              trend === "down" ? "text-error"   : "text-text-muted"
            )}>
              {trend === "up"   ? <TrendingUp  size={10} /> :
               trend === "down" ? <TrendingDown size={10} /> :
               <Minus size={10} />}
              {trendValue}
            </span>
          )}
          {sub && <span className="text-[10px] text-text-faint font-mono">{sub}</span>}
        </div>
      )}
    </div>
  );
}