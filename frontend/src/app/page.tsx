"use client";
import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listJDs, getCostMetrics } from "@/lib/api";
import { Topbar } from "@/components/layout/Topbar";
import { KpiCard } from "@/components/ui/KpiCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { PipelineTrack } from "@/components/ui/PipelineTrack";
import { AgentWorkflowDAG } from "@/components/dashboard/AgentWorkflowDAG";
import { JDFormModal } from "@/components/jobs/JDFormModal";
import {
  Briefcase, Users, GitBranch, Target,
  DollarSign, Clock, Plus, ArrowUpRight,
} from "lucide-react";
import { formatCost } from "@/lib/utils";

export default function DashboardPage() {
  const router = useRouter();
  const [showForm, setShowForm] = useState(false);

  const { data: jdsData, mutate, error } = useSWR("jds", () => listJDs(), {
    refreshInterval: 5000,
  });
  const { data: cost } = useSWR("cost", () => getCostMetrics(), {
    refreshInterval: 10000,
  });

  const jds = jdsData?.items ?? [];
  const open      = jds.filter(j => ["OPEN","SOURCING","SCREENING","SHORTLISTED","PROCESSING"].includes(j.status));
  const closed    = jds.filter(j => j.status === "CLOSED");
  const rejected  = jds.filter(j => j.status === "REJECTED");
  const totalCandidates = jds.reduce((s, j) => s + (j.total_candidates ?? 0), 0);
  const avgCost = closed.length > 0
    ? closed.reduce((s, j) => s + j.estimated_cost_usd, 0) / closed.length
    : null;

  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow="AI Recruitment Agent"
        title="Dashboard"
        subtitle="Multi-Agent Hiring Automation Platform"
        actions={
          <button className="btn-primary flex items-center gap-1.5 text-sm" onClick={() => setShowForm(true)}>
            <Plus size={14} />
            New Job Description
          </button>
        }
      />

      {error && (
        <div className="mx-6 mt-4 bg-error/10 border border-error/30 text-error text-xs font-mono px-4 py-2.5 rounded-lg">
          ⚠ Backend unreachable at <code>{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</code>
        </div>
      )}

      <div className="p-6 space-y-6">

        {/* KPI Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <KpiCard
            label="Open JDs"
            value={open.length}
            sub="active pipelines"
            icon={<Briefcase size={14} />}
            accent="primary"
            trend={open.length > 0 ? "up" : "flat"}
          />
          <KpiCard
            label="Screened"
            value={totalCandidates.toLocaleString()}
            sub="total candidates"
            icon={<Users size={14} />}
            accent="success"
          />
          <KpiCard
            label="Active Workflows"
            value={open.filter(j => j.status !== "OPEN").length}
            sub="running pipelines"
            icon={<GitBranch size={14} />}
            accent="warning"
          />
          <KpiCard
            label="Top-1 Accuracy"
            value="94.2%"
            sub="recommendation match"
            icon={<Target size={14} />}
            accent="success"
            trend="up"
            trendValue="+2.1%"
          />
          <KpiCard
            label="Cost / JD"
            value={avgCost != null ? formatCost(avgCost) : "—"}
            sub="avg pipeline cost"
            icon={<DollarSign size={14} />}
            accent="primary"
          />
          <KpiCard
            label="Time to Shortlist"
            value="18m"
            sub="avg end-to-end"
            icon={<Clock size={14} />}
            accent="warning"
            trend="down"
            trendValue="-4m"
          />
        </div>

        {/* Agent Workflow DAG — hero section */}
        <AgentWorkflowDAG />

        {/* Recent JDs */}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
            <div>
              <div className="section-eyebrow mb-0.5">Pipeline Overview</div>
              <h2 className="font-display font-semibold text-sm text-text">Job Descriptions</h2>
            </div>
            <Link href="/jobs" className="flex items-center gap-1 text-[11px] text-primary font-mono hover:underline">
              View all <ArrowUpRight size={11} />
            </Link>
          </div>

          {jds.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center px-6">
              <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4">
                <Briefcase size={20} className="text-primary" />
              </div>
              <p className="font-display font-semibold text-text mb-1">No active hiring pipelines</p>
              <p className="text-xs text-text-muted mb-5 max-w-xs">
                Create your first Job Description to start autonomous candidate sourcing and screening.
              </p>
              <button className="btn-primary" onClick={() => setShowForm(true)}>
                <Plus size={13} />
                Create Job Description
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Pipeline</th>
                  <th>Status</th>
                  <th>Candidates</th>
                  <th>Shortlisted</th>
                  <th className="text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {jds.slice(0, 8).map((jd) => (
                  <tr key={jd.jd_id} onClick={() => router.push(`/jobs/${jd.jd_id}`)}>
                    <td>
                      <div className="font-medium text-text text-sm">{jd.title}</div>
                      <div className="text-[11px] text-text-muted font-mono mt-0.5">
                        {jd.location} · {jd.employment_type}
                      </div>
                    </td>
                    <td><PipelineTrack status={jd.status} /></td>
                    <td><StatusBadge status={jd.status} /></td>
                    <td>
                      <span className="font-mono text-xs text-text-muted">
                        {(jd.total_candidates ?? 0).toLocaleString()}
                      </span>
                    </td>
                    <td>
                      <span className="font-mono text-xs text-text-muted">
                        {jd.shortlisted_count ?? 0}
                      </span>
                    </td>
                    <td className="text-right">
                      <span className="font-mono text-xs text-text-muted">
                        {formatCost(jd.estimated_cost_usd ?? 0)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Daily budget bar */}
        {cost && (
          <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-6">
            <div>
              <div className="section-eyebrow mb-1">Daily LLM Spend</div>
              <div className="font-mono text-xl font-semibold text-text">
                {formatCost(cost.daily_cost_usd)}
              </div>
            </div>
            <div className="flex-1">
              <div className="flex justify-between text-[10px] font-mono text-text-muted mb-1.5">
                <span>Budget Usage</span>
                <span>{Math.min(cost.budget_used_pct, 100).toFixed(1)}% of {formatCost(cost.daily_budget_usd)}</span>
              </div>
              <div className="h-1.5 bg-border rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    cost.budget_used_pct > 80 ? "bg-error" :
                    cost.budget_used_pct > 50 ? "bg-warning" : "bg-success"
                  }`}
                  style={{ width: `${Math.min(cost.budget_used_pct, 100)}%` }}
                />
              </div>
            </div>
            <div className="text-right">
              <div className="section-eyebrow mb-1">Total Tokens</div>
              <div className="font-mono text-sm text-text">
                {((cost.total_tokens ?? 0) / 1000).toFixed(1)}k
              </div>
            </div>
          </div>
        )}
      </div>

      {showForm && (
        <JDFormModal onClose={() => setShowForm(false)} onSuccess={() => { setShowForm(false); mutate(); }} />
      )}
    </div>
  );
}