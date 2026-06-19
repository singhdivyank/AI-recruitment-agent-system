"use client";
import { Topbar } from "@/components/layout/Topbar";
import { KpiCard } from "@/components/ui/KpiCard";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from "recharts";
import { BarChart3, Target, Brain } from "lucide-react";

const RETRIEVAL_DATA = [
  { name: "JD-001", recall: 0.91, precision: 0.87, ndcg: 0.89 },
  { name: "JD-002", recall: 0.88, precision: 0.84, ndcg: 0.86 },
  { name: "JD-003", recall: 0.94, precision: 0.91, ndcg: 0.93 },
  { name: "JD-004", recall: 0.86, precision: 0.82, ndcg: 0.84 },
  { name: "JD-005", recall: 0.92, precision: 0.89, ndcg: 0.91 },
];

const RANKING_TREND = [
  { day: "Mon", top1: 90, top3: 96, top5: 99 },
  { day: "Tue", top1: 92, top3: 97, top5: 99 },
  { day: "Wed", top1: 89, top3: 95, top5: 98 },
  { day: "Thu", top1: 94, top3: 98, top5: 100 },
  { day: "Fri", top1: 94, top3: 97, top5: 99 },
];

const CHART_TOOLTIP_STYLE = {
  contentStyle: { background: "#1F2937", border: "1px solid #374151", borderRadius: 8, fontSize: 11, fontFamily: "monospace" },
  labelStyle: { color: "#9CA3AF" },
};

export default function EvaluationPage() {
  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow="RAG Evaluation & Observability"
        title="Evaluation Metrics"
        subtitle="End-to-end pipeline quality benchmarks"
      />

      <div className="p-6 space-y-6">
        {/* Retrieval metrics */}
        <div>
          <div className="section-eyebrow mb-3 flex items-center gap-2">
            <BarChart3 size={11} /> Retrieval Quality
          </div>
          <div className="grid grid-cols-4 gap-3">
            <KpiCard label="Recall@10"    value="0.912" sub="avg across JDs" accent="success" trend="up" trendValue="+0.03" />
            <KpiCard label="Precision@10" value="0.874" sub="avg across JDs" accent="primary" />
            <KpiCard label="NDCG@10"      value="0.891" sub="normalized discount" accent="success" />
            <KpiCard label="MRR"          value="0.836" sub="mean reciprocal rank" accent="warning" />
          </div>
        </div>

        {/* Retrieval chart */}
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="section-eyebrow mb-4">Per-JD Retrieval Metrics</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={RETRIEVAL_DATA} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#9CA3AF", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0.8, 1]} tick={{ fontSize: 10, fill: "#9CA3AF", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Bar dataKey="recall"    fill="#6366F1" radius={[3,3,0,0]} name="Recall" />
              <Bar dataKey="precision" fill="#10B981" radius={[3,3,0,0]} name="Precision" />
              <Bar dataKey="ndcg"      fill="#F59E0B" radius={[3,3,0,0]} name="NDCG" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Screening metrics */}
        <div>
          <div className="section-eyebrow mb-3 flex items-center gap-2">
            <Brain size={11} /> Screening Quality
          </div>
          <div className="grid grid-cols-4 gap-3">
            <KpiCard label="Human Agreement"    value="91.3%" sub="vs manual review"  accent="success" trend="up" trendValue="+1.2%" />
            <KpiCard label="Hallucination Rate" value="0.8%"  sub="LLM accuracy check" accent="success" trend="down" trendValue="-0.3%" />
            <KpiCard label="Grounding Score"    value="0.943" sub="citation coverage"  accent="primary" />
            <KpiCard label="Citation Coverage"  value="87.2%" sub="evidence-backed"    accent="warning" />
          </div>
        </div>

        {/* Ranking metrics */}
        <div>
          <div className="section-eyebrow mb-3 flex items-center gap-2">
            <Target size={11} /> Ranking Accuracy
          </div>
          <div className="grid grid-cols-4 gap-3">
            <KpiCard label="Top-1 Accuracy"   value="94.2%" sub="correct top pick"      accent="success" trend="up" trendValue="+2.1%" />
            <KpiCard label="Top-3 Accuracy"   value="97.8%" sub="in top 3"              accent="success" />
            <KpiCard label="Top-5 Accuracy"   value="99.1%" sub="in top 5"              accent="success" />
            <KpiCard label="Acceptance Rate"  value="88.4%" sub="recruiter acceptance"  accent="primary" trend="up" trendValue="+5.2%" />
          </div>
        </div>

        {/* Ranking trend */}
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="section-eyebrow mb-4">Ranking Accuracy Trend (This Week)</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={RANKING_TREND}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#9CA3AF", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
              <YAxis domain={[85, 100]} tick={{ fontSize: 10, fill: "#9CA3AF", fontFamily: "monospace" }} axisLine={false} tickLine={false} />
              <Tooltip {...CHART_TOOLTIP_STYLE} formatter={(v) => `${v}%`} />
              <Line type="monotone" dataKey="top1" stroke="#6366F1" strokeWidth={2} dot={false} name="Top-1" />
              <Line type="monotone" dataKey="top3" stroke="#10B981" strokeWidth={2} dot={false} name="Top-3" />
              <Line type="monotone" dataKey="top5" stroke="#F59E0B" strokeWidth={1.5} dot={false} name="Top-5" strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-5 mt-2 justify-end">
            {[["Top-1", "#6366F1"], ["Top-3", "#10B981"], ["Top-5", "#F59E0B"]].map(([l, c]) => (
              <div key={l} className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted">
                <div className="w-3 h-0.5 rounded" style={{ background: c }} />
                {l}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}