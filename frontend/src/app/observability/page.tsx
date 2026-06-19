"use client";
import { Topbar } from "@/components/layout/Topbar";
import { KpiCard } from "@/components/ui/KpiCard";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { Activity, Cpu } from "lucide-react";

const HOURS = Array.from({ length: 24 }, (_, i) => ({
  h: `${String(i).padStart(2,"0")}:00`,
  tokens: Math.floor(Math.random() * 50000 + 10000),
  latency: Math.floor(Math.random() * 800 + 400),
  cost: parseFloat((Math.random() * 0.08 + 0.02).toFixed(4)),
  errors: Math.floor(Math.random() * 3),
}));

const TOOL_CALLS = [
  { tool: "linkedin_search", calls: 1243, success: 99.1 },
  { tool: "naukri_search",   calls: 983,  success: 98.4 },
  { tool: "ats_fetch",       calls: 721,  success: 99.7 },
  { tool: "llm_screen",      calls: 3512, success: 97.8 },
  { tool: "llm_rank",        calls: 428,  success: 99.3 },
  { tool: "email_draft",     calls: 214,  success: 96.2 },
];

const TOOLTIP = {
  contentStyle: { background: "#1F2937", border: "1px solid #374151", borderRadius: 8, fontSize: 11, fontFamily: "monospace" },
  labelStyle: { color: "#9CA3AF" },
};

export default function ObservabilityPage() {
  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow="LLM Operations"
        title="Observability"
        subtitle="Real-time system telemetry and LLM metrics"
      />

      <div className="p-6 space-y-6">
        {/* System KPIs */}
        <div>
          <div className="section-eyebrow mb-3 flex items-center gap-2">
            <Activity size={11} /> System Health
          </div>
          <div className="grid grid-cols-5 gap-3">
            <KpiCard label="API Latency"    value="124ms"  sub="p50 response"   accent="success" trend="down" trendValue="-12ms" />
            <KpiCard label="Agent Latency"  value="1.42s"  sub="avg per call"   accent="warning" />
            <KpiCard label="Tool Latency"   value="89ms"   sub="MCP avg"        accent="success" />
            <KpiCard label="Error Rate"     value="0.42%"  sub="last 24h"       accent="success" trend="down" trendValue="-0.1%" />
            <KpiCard label="Throughput"     value="98.8%"  sub="workflow completion" accent="success" />
          </div>
        </div>

        {/* LLM Metrics */}
        <div>
          <div className="section-eyebrow mb-3 flex items-center gap-2">
            <Cpu size={11} /> LLM Metrics
          </div>
          <div className="grid grid-cols-5 gap-3">
            <KpiCard label="Prompt Tokens"      value="824k"   sub="today"         accent="primary" />
            <KpiCard label="Completion Tokens"  value="312k"   sub="today"         accent="primary" />
            <KpiCard label="Total Tokens"       value="1.14M"  sub="today"         accent="primary" trend="up" trendValue="+8%" />
            <KpiCard label="Cost / JD"          value="$0.0214" sub="avg today"    accent="warning" />
            <KpiCard label="Daily Spend"        value="$2.47"  sub="of $10 budget" accent="success" />
          </div>
        </div>

        {/* Charts grid */}
        <div className="grid grid-cols-2 gap-5">
          {/* Token usage */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="section-eyebrow mb-4">Token Usage — 24h</div>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={HOURS}>
                <defs>
                  <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#6366F1" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#6366F1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                <XAxis dataKey="h" tick={{ fontSize: 9, fill: "#4B5563", fontFamily: "monospace" }} axisLine={false} tickLine={false} interval={5} />
                <YAxis tick={{ fontSize: 9, fill: "#4B5563", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP} />
                <Area type="monotone" dataKey="tokens" stroke="#6366F1" strokeWidth={1.5} fill="url(#tokenGrad)" name="Tokens" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Latency trend */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="section-eyebrow mb-4">Agent Latency Trend — 24h</div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={HOURS}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                <XAxis dataKey="h" tick={{ fontSize: 9, fill: "#4B5563", fontFamily: "monospace" }} axisLine={false} tickLine={false} interval={5} />
                <YAxis tick={{ fontSize: 9, fill: "#4B5563", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP} formatter={(v) => `${v}ms`} />
                <Line type="monotone" dataKey="latency" stroke="#F59E0B" strokeWidth={1.5} dot={false} name="Latency (ms)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Cost trend */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="section-eyebrow mb-4">Cost Trend — 24h</div>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={HOURS}>
                <defs>
                  <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#10B981" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                <XAxis dataKey="h" tick={{ fontSize: 9, fill: "#4B5563", fontFamily: "monospace" }} axisLine={false} tickLine={false} interval={5} />
                <YAxis tick={{ fontSize: 9, fill: "#4B5563", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP} formatter={(v: number | string) => `$${v}`} />
                <Area type="monotone" dataKey="cost" stroke="#10B981" strokeWidth={1.5} fill="url(#costGrad)" name="Cost ($)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Tool call volume */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="section-eyebrow mb-4">Tool Call Volume</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={TOOL_CALLS} layout="vertical" barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 9, fill: "#4B5563", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="tool" tick={{ fontSize: 9, fill: "#9CA3AF", fontFamily: "monospace" }} axisLine={false} tickLine={false} width={90} />
                <Tooltip {...TOOLTIP} />
                <Bar dataKey="calls" fill="#6366F1" radius={[0,3,3,0]} name="Calls" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}