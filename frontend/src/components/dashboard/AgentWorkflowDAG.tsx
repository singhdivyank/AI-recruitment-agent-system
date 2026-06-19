"use client";
import { cn } from "@/lib/utils";
import type { AgentNode } from "@/types";
import { CheckCircle2, Circle, Loader2, AlertCircle, Clock } from "lucide-react";

const DEFAULT_NODES: AgentNode[] = [
  { id: "intake",      label: "JD Intake",      description: "Parse & validate",     status: "done",    avg_latency_ms: 340,  success_rate: 100,  total_calls: 48 },
  { id: "compliance",  label: "Compliance",     description: "Bias & legal check",   status: "done",    avg_latency_ms: 210,  success_rate: 98.1, total_calls: 48 },
  { id: "sourcing",    label: "Sourcing",       description: "Multi-MCP retrieval",  status: "running", avg_latency_ms: 1840, success_rate: 99.2, total_calls: 44 },
  { id: "normalize",   label: "Normalization",  description: "Dedup & enrich",       status: "pending", avg_latency_ms: 520,  success_rate: 97.4, total_calls: 38 },
  { id: "screening",   label: "Screening",      description: "LLM eval per criteria",status: "pending", avg_latency_ms: 2300, success_rate: 96.8, total_calls: 35 },
  { id: "ranking",     label: "Ranking",        description: "Score & rank",         status: "pending", avg_latency_ms: 680,  success_rate: 99.0, total_calls: 28 },
  { id: "outreach",    label: "Outreach",       description: "Draft & dispatch",     status: "pending", avg_latency_ms: 890,  success_rate: 95.3, total_calls: 22 },
];

const STATUS_ICON = {
  done:    <CheckCircle2 size={14} className="text-success" />,
  running: <Loader2     size={14} className="text-primary animate-spin" />,
  pending: <Circle      size={14} className="text-text-faint" />,
  idle:    <Circle      size={14} className="text-text-faint" />,
  failed:  <AlertCircle size={14} className="text-error" />,
};

interface AgentWorkflowProps {
  nodes?: AgentNode[];
}

export function AgentWorkflowDAG({ nodes = DEFAULT_NODES }: AgentWorkflowProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="section-eyebrow mb-1">Live Pipeline</div>
          <h2 className="font-display font-semibold text-base text-text">Agent Workflow</h2>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-warning bg-warning/10 border border-warning/20 px-2.5 py-1 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-warning animate-pulse inline-block" />
          Pipeline Running
        </div>
      </div>

      {/* The DAG — horizontal flow */}
      <div className="relative overflow-x-auto pb-2">
        <div className="flex items-start gap-0 min-w-max">
          {nodes.map((node, i) => (
            <div key={node.id} className="flex items-start">
              {/* Node */}
              <div className={cn(
                "agent-node relative",
                `agent-node-${node.status}`,
                node.status === "running" ? "running-pulse" : ""
              )}>
                <div className="flex items-center gap-1.5 mb-1">
                  {STATUS_ICON[node.status]}
                  <span className="text-[11px] font-semibold font-display whitespace-nowrap">
                    {node.label}
                  </span>
                </div>
                <span className="text-[9px] text-text-faint font-mono whitespace-nowrap">
                  {node.description}
                </span>

                {/* Metrics tooltip-style */}
                {node.avg_latency_ms != null && (
                  <div className="mt-2 flex flex-col gap-0.5">
                    <span className={cn(
                      "text-[9px] font-mono",
                      node.status === "done" ? "text-success" :
                      node.status === "running" ? "text-primary" : "text-text-faint"
                    )}>
                      <Clock size={8} className="inline mr-0.5" />
                      {node.avg_latency_ms >= 1000
                        ? `${(node.avg_latency_ms / 1000).toFixed(1)}s`
                        : `${node.avg_latency_ms}ms`}
                    </span>
                    {node.success_rate != null && (
                      <span className={cn(
                        "text-[9px] font-mono",
                        node.status === "pending" ? "text-text-faint" : "text-text-muted"
                      )}>
                        {node.success_rate.toFixed(1)}% ok
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Connector */}
              {i < nodes.length - 1 && (
                <div className="flex items-center mt-5 mx-1">
                  <svg width="32" height="12" viewBox="0 0 32 12" fill="none">
                    <line
                      x1="0" y1="6" x2="28" y2="6"
                      className={cn(
                        node.status === "running" ? "flow-line-animated stroke-primary" : node.status === "done" ? "stroke-primary" : "stroke-border"
                      )}
                      strokeWidth="1.5"
                      strokeDasharray={node.status === "running" ? "8 4" : undefined}
                    />
                    <polygon
                      points="28,3 32,6 28,9"
                      className={node.status === "done" ? "fill-primary" : "fill-border"}
                    />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Stage legend */}
      <div className="mt-4 pt-4 border-t border-border flex items-center gap-5">
        {[
          { status: "done",    label: "Complete" },
          { status: "running", label: "Running" },
          { status: "pending", label: "Queued" },
        ].map(({ status, label }) => (
          <div key={status} className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted">
            {STATUS_ICON[status as keyof typeof STATUS_ICON]}
            {label}
          </div>
        ))}
        <div className="ml-auto text-[10px] font-mono text-text-faint">
          {nodes.filter(n => n.status === "done").length}/{nodes.length} stages complete
        </div>
      </div>
    </div>
  );
}