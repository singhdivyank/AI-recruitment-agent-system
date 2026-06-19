"use client";
import { Topbar } from "@/components/layout/Topbar";
import { AgentWorkflowDAG } from "@/components/dashboard/AgentWorkflowDAG";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { GitBranch, Zap, CheckCircle2, XCircle, Activity } from "lucide-react";

const MOCK_EXECUTIONS = [
  { ts: "14:32:01", agent: "Compliance Agent",   action: "Validate JD",           duration: "210ms",  tokens: 842,   status: "done" },
  { ts: "14:32:15", agent: "Sourcing Agent",      action: "LinkedIn MCP Search",   duration: "1.84s",  tokens: 1240,  status: "running" },
  { ts: "14:32:15", agent: "Sourcing Agent",      action: "Naukri MCP Search",     duration: "2.10s",  tokens: 1180,  status: "running" },
  { ts: "14:31:44", agent: "Screening Agent",     action: "Evaluate Candidate",    duration: "2.30s",  tokens: 1843,  status: "done" },
  { ts: "14:31:22", agent: "Normalization Agent", action: "Dedup & Enrich",        duration: "520ms",  tokens: 640,   status: "done" },
  { ts: "14:30:58", agent: "Ranking Agent",       action: "Score & Rank",          duration: "680ms",  tokens: 920,   status: "done" },
  { ts: "14:30:10", agent: "Outreach Agent",      action: "Draft Outreach Email",  duration: "890ms",  tokens: 1420,  status: "done" },
  { ts: "14:28:40", agent: "JD Intake Agent",     action: "Parse JD",              duration: "340ms",  tokens: 520,   status: "done" },
];

const AGENT_STATS = [
  { name: "JD Intake Agent",     calls: 48,  success: 100,  avg_ms: 340,  status: "idle" },
  { name: "Compliance Agent",    calls: 48,  success: 98.1, avg_ms: 210,  status: "idle" },
  { name: "Sourcing Agent",      calls: 44,  success: 99.2, avg_ms: 1840, status: "running" },
  { name: "Normalization Agent", calls: 38,  success: 97.4, avg_ms: 520,  status: "idle" },
  { name: "Screening Agent",     calls: 35,  success: 96.8, avg_ms: 2300, status: "idle" },
  { name: "Ranking Agent",       calls: 28,  success: 99.0, avg_ms: 680,  status: "idle" },
  { name: "Outreach Agent",      calls: 22,  success: 95.3, avg_ms: 890,  status: "idle" },
];

export default function WorkflowsPage() {
  const active   = AGENT_STATS.filter(a => a.status === "running").length;
  const totalCalls = AGENT_STATS.reduce((s, a) => s + a.calls, 0);
  const avgSuccess = (AGENT_STATS.reduce((s, a) => s + a.success, 0) / AGENT_STATS.length).toFixed(1);

  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow="Multi-Agent System"
        title="Agent Workflows"
        subtitle="LangGraph-orchestrated autonomous hiring pipeline"
      />

      <div className="p-6 space-y-5">
        {/* Stats row */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Active Agents",           value: active,      icon: <Activity size={14} />,    color: "text-warning" },
            { label: "Total Tool Calls",        value: totalCalls,  icon: <Zap size={14} />,        color: "text-primary" },
            { label: "Avg Success Rate",        value: `${avgSuccess}%`, icon: <CheckCircle2 size={14} />, color: "text-success" },
            { label: "Failed Workflows",        value: 0,           icon: <XCircle size={14} />,    color: "text-text-muted" },
          ].map(({ label, value, icon, color }) => (
            <div key={label} className="metric-card flex items-center gap-3">
              <span className={`${color} mt-0.5`}>{icon}</span>
              <div>
                <div className="section-eyebrow">{label}</div>
                <div className={`font-mono font-semibold text-lg ${color}`}>{value}</div>
              </div>
            </div>
          ))}
        </div>

        {/* DAG visualization */}
        <AgentWorkflowDAG />

        {/* Agent registry table */}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <div className="section-eyebrow mb-0.5">Agent Registry</div>
            <h2 className="font-display font-semibold text-sm text-text">Registered Agents</h2>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Status</th>
                <th>Total Calls</th>
                <th>Avg Latency</th>
                <th>Success Rate</th>
              </tr>
            </thead>
            <tbody>
              {AGENT_STATS.map(a => (
                <tr key={a.name} className="cursor-default hover:bg-card/80">
                  <td>
                    <div className="flex items-center gap-2">
                      <GitBranch size={13} className="text-text-faint" />
                      <span className="font-medium text-text text-sm">{a.name}</span>
                    </div>
                  </td>
                  <td><StatusBadge status={a.status === "running" ? "PROCESSING" : "CLOSED"} /></td>
                  <td><span className="font-mono text-xs text-text-muted">{a.calls}</span></td>
                  <td>
                    <span className="font-mono text-xs text-text-muted">
                      {a.avg_ms >= 1000 ? `${(a.avg_ms / 1000).toFixed(2)}s` : `${a.avg_ms}ms`}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1 bg-border rounded-full overflow-hidden">
                        <div className="h-full bg-success rounded-full" style={{ width: `${a.success}%` }} />
                      </div>
                      <span className="font-mono text-xs text-text-muted">{a.success}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Execution log */}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <div className="section-eyebrow mb-0.5">Execution Log</div>
            <h2 className="font-display font-semibold text-sm text-text">Recent Agent Actions</h2>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Agent</th>
                <th>Action</th>
                <th>Duration</th>
                <th>Tokens</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_EXECUTIONS.map((e, i) => (
                <tr key={i} className="cursor-default">
                  <td><span className="font-mono text-[10px] text-text-faint">{e.ts}</span></td>
                  <td><span className="text-xs text-text font-medium">{e.agent}</span></td>
                  <td><span className="text-xs text-text-muted">{e.action}</span></td>
                  <td><span className="font-mono text-xs text-text-muted">{e.duration}</span></td>
                  <td><span className="font-mono text-xs text-text-muted">{e.tokens.toLocaleString()}</span></td>
                  <td><StatusBadge status={e.status === "done" ? "CLOSED" : "PROCESSING"} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}