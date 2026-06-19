"use client";
import { Topbar } from "@/components/layout/Topbar";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Plug, Zap, Clock, CheckCircle2 } from "lucide-react";

const MCP_PROVIDERS = [
  {
    id: "linkedin",    name: "LinkedIn MCP",   icon: "💼",
    status: "healthy", latency_ms: 82,  tool_calls: 12431, success_rate: 99.1, availability: 99.9,
    description: "Professional network candidate sourcing via MCP tool protocol",
    tools: ["search_profiles","fetch_profile","get_connections"],
  },
  {
    id: "naukri",      name: "Naukri MCP",     icon: "🔍",
    status: "healthy", latency_ms: 110, tool_calls: 9831,  success_rate: 98.4, availability: 99.5,
    description: "South Asia job market integration for regional talent sourcing",
    tools: ["search_candidates","get_resume","filter_experience"],
  },
  {
    id: "ats",         name: "ATS MCP",        icon: "📋",
    status: "healthy", latency_ms: 45,  tool_calls: 7214,  success_rate: 99.7, availability: 100,
    description: "Internal applicant tracking system connector",
    tools: ["list_applicants","get_application","update_status"],
  },
  {
    id: "email",       name: "Email MCP",      icon: "✉️",
    status: "healthy", latency_ms: 230, tool_calls: 1842,  success_rate: 97.2, availability: 98.8,
    description: "Outreach dispatch and reply tracking",
    tools: ["send_email","get_thread","track_open"],
  },
];

export default function IntegrationsPage() {
  const total = MCP_PROVIDERS.reduce((s, p) => s + p.tool_calls, 0);
  const avgLatency = Math.round(MCP_PROVIDERS.reduce((s, p) => s + p.latency_ms, 0) / MCP_PROVIDERS.length);
  const healthy = MCP_PROVIDERS.filter(p => p.status === "healthy").length;

  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow="Model Context Protocol"
        title="MCP Integrations"
        subtitle="Connected tool providers powering the multi-agent pipeline"
      />

      <div className="p-6 space-y-5">
        {/* Summary */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Connected MCPs",   value: healthy + "/" + MCP_PROVIDERS.length, icon: <Plug size={13} />,         color: "text-success" },
            { label: "Total Tool Calls", value: total.toLocaleString(),               icon: <Zap size={13} />,          color: "text-primary" },
            { label: "Avg Latency",      value: `${avgLatency}ms`,                   icon: <Clock size={13} />,        color: "text-warning" },
            { label: "All Healthy",      value: healthy === MCP_PROVIDERS.length ? "Yes" : "No",
              icon: <CheckCircle2 size={13} />, color: "text-success" },
          ].map(({ label, value, icon, color }) => (
            <div key={label} className="metric-card flex items-center gap-3">
              <span className={`${color}`}>{icon}</span>
              <div>
                <div className="section-eyebrow">{label}</div>
                <div className={`font-mono font-semibold text-lg ${color}`}>{value}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Provider cards */}
        <div className="grid grid-cols-2 gap-4">
          {MCP_PROVIDERS.map(p => (
            <div key={p.id} className="bg-card border border-border rounded-xl p-5 hover:border-primary/30 transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="text-2xl">{p.icon}</div>
                  <div>
                    <h3 className="font-display font-semibold text-sm text-text">{p.name}</h3>
                    <p className="text-[11px] text-text-muted mt-0.5">{p.description}</p>
                  </div>
                </div>
                <StatusBadge status={p.status} size="md" />
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-4 gap-3 mb-4">
                {[
                  { label: "Latency",     value: `${p.latency_ms}ms`, color: p.latency_ms < 100 ? "text-success" : "text-warning" },
                  { label: "Tool Calls",  value: p.tool_calls.toLocaleString(), color: "text-primary" },
                  { label: "Success",     value: `${p.success_rate}%`, color: "text-success" },
                  { label: "Uptime",      value: `${p.availability}%`, color: "text-success" },
                ].map(({ label, value, color }) => (
                  <div key={label}>
                    <div className="section-eyebrow mb-0.5">{label}</div>
                    <div className={`font-mono text-sm font-semibold ${color}`}>{value}</div>
                  </div>
                ))}
              </div>

              {/* Availability bar */}
              <div className="mb-4">
                <div className="flex justify-between text-[10px] font-mono text-text-faint mb-1">
                  <span>Availability</span>
                  <span>{p.availability}%</span>
                </div>
                <div className="h-1 bg-border rounded-full overflow-hidden">
                  <div className="h-full bg-success rounded-full" style={{ width: `${p.availability}%` }} />
                </div>
              </div>

              {/* Tools */}
              <div>
                <div className="section-eyebrow mb-2">Exposed Tools</div>
                <div className="flex flex-wrap gap-1.5">
                  {p.tools.map(t => (
                    <span key={t} className="text-[9px] font-mono bg-bg border border-border text-text-muted px-1.5 py-0.5 rounded">
                      {t}()
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}