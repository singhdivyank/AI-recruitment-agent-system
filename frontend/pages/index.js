import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { listJDs, getCostMetrics } from "../services/api";
import JDForm from "../components/jd/JDForm";
import StatusBadge from "../components/dashboard/StatusBadge";
import MetricsBar from "../components/dashboard/MetricsBar";

export default function Dashboard() {
  const {
    data: jdsData,
    mutate: mutateJDs,
    error: jdsError,
  } = useSWR("jds", () => listJDs(), { refreshInterval: 5000 });

  const { data: costData } = useSWR("cost", () => getCostMetrics(), {
    refreshInterval: 10000,
  });

  const [showForm, setShowForm] = useState(false);

  const jds = jdsData?.items || [];
  const open = jds.filter((j) =>
    ["OPEN", "SOURCING", "SCREENING", "SHORTLISTED", "PROCESSING"].includes(j.status)
  );
  const closed = jds.filter((j) => j.status === "CLOSED");
  const rejected = jds.filter((j) => j.status === "REJECTED");

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">🤖 AI Recruitment Agent</h1>
            <p className="text-sm text-gray-500">Multi-agent hiring automation</p>
          </div>
          <button className="btn-primary" onClick={() => setShowForm(true)}>
            + New JD
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {jdsError && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg mb-6">
            ⚠️ Could not reach the backend. Is it running at{" "}
            <span className="font-mono">{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</span>?
          </div>
        )}

        {/* Cost Metrics Bar */}
        {costData && (
          <MetricsBar
            cost={costData}
            jdCounts={{ open: open.length, closed: closed.length, rejected: rejected.length }}
          />
        )}

        {/* Funnel stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: "Open JDs", count: open.length, color: "text-green-600" },
            { label: "Closed JDs", count: closed.length, color: "text-gray-600" },
            { label: "Rejected (Compliance)", count: rejected.length, color: "text-red-600" },
          ].map((s) => (
            <div key={s.label} className="card text-center">
              <div className={`text-3xl font-bold ${s.color}`}>{s.count}</div>
              <div className="text-sm text-gray-500 mt-1">{s.label}</div>
            </div>
          ))}
        </div>

        {/* JD List */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Job Descriptions</h2>
          {jds.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <p className="text-4xl mb-3">📋</p>
              <p>No JDs yet. Submit your first one!</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {jds.map((jd) => (
                <Link
                  key={jd.jd_id}
                  href={`/jd/${jd.jd_id}`}
                  className="flex items-center justify-between py-4 hover:bg-gray-50 -mx-6 px-6 transition-colors"
                >
                  <div>
                    <div className="font-medium text-gray-900">{jd.title}</div>
                    <div className="text-sm text-gray-500 mt-0.5">
                      {jd.location} · {jd.employment_type} ·{" "}
                      <span className="text-gray-400">{jd.total_candidates || 0} candidates</span>
                    </div>
                    <div className="flex gap-2 mt-1">
                      {(jd.must_have_skills || []).slice(0, 3).map((s) => (
                        <span key={s} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right text-sm text-gray-400">
                      ${(jd.estimated_cost_usd || 0).toFixed(3)}
                    </div>
                    <StatusBadge status={jd.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* JD Submission Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-100 flex justify-between items-center">
              <h2 className="text-lg font-semibold">Submit New Job Description</h2>
              <button
                onClick={() => setShowForm(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl"
              >
                ×
              </button>
            </div>
            <JDForm
              onSuccess={() => {
                setShowForm(false);
                mutateJDs();
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
