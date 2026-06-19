"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { listJDs } from "@/lib/api";
import { Topbar } from "@/components/layout/Topbar";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { PipelineTrack } from "@/components/ui/PipelineTrack";
import { JDFormModal } from "@/components/jobs/JDFormModal";
import { formatCost } from "@/lib/utils";
import { Plus, Search, Briefcase } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function JobsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data, mutate, error } = useSWR("jds-list", () => listJDs(), { refreshInterval: 5000 });
  const jds = (data?.items ?? []).filter(j =>
    j.title.toLowerCase().includes(search.toLowerCase()) ||
    j.location.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow="Pipeline Management"
        title="Job Descriptions"
        subtitle={`${jds.length} positions`}
        actions={
          <>
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-faint" />
              <input
                className="field-input pl-7 py-1.5 text-xs w-48"
                placeholder="Search roles…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <button className="btn-primary text-xs" onClick={() => setShowForm(true)}>
              <Plus size={13} /> New JD
            </button>
          </>
        }
      />

      {error && (
        <div className="mx-6 mt-4 bg-error/10 border border-error/30 text-error text-xs font-mono px-4 py-2.5 rounded-lg">
          Backend unreachable
        </div>
      )}

      <div className="p-6">
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          {jds.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center px-6">
              <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4">
                <Briefcase size={20} className="text-primary" />
              </div>
              <p className="font-display font-semibold text-text mb-1">No job descriptions yet</p>
              <p className="text-xs text-text-muted mb-5 max-w-xs">
                Create your first JD to start autonomous candidate sourcing and screening.
              </p>
              <button className="btn-primary" onClick={() => setShowForm(true)}>
                <Plus size={13} /> Create Job Description
              </button>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>JD Title</th>
                  <th>Pipeline</th>
                  <th>Status</th>
                  <th>Retrieved</th>
                  <th>Shortlisted</th>
                  <th>Created</th>
                  <th className="text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {jds.map(jd => (
                  <tr key={jd.jd_id} onClick={() => router.push(`/jobs/${jd.jd_id}`)}>
                    <td>
                      <div className="font-semibold text-text text-sm">{jd.title}</div>
                      <div className="text-[11px] text-text-muted font-mono mt-0.5">
                        {jd.location} · {jd.employment_type}
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(jd.must_have_skills ?? []).slice(0, 3).map(s => (
                          <span key={s} className="text-[9px] font-mono border border-border/80 bg-bg px-1.5 py-0.5 rounded text-text-muted">
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td><PipelineTrack status={jd.status} /></td>
                    <td><StatusBadge status={jd.status} /></td>
                    <td><span className="font-mono text-xs text-text-muted">{(jd.total_candidates ?? 0).toLocaleString()}</span></td>
                    <td><span className="font-mono text-xs text-text-muted">{jd.shortlisted_count ?? 0}</span></td>
                    <td>
                      <span className="font-mono text-xs text-text-muted">
                        {jd.created_at
                          ? formatDistanceToNow(new Date(jd.created_at), { addSuffix: true })
                          : "—"}
                      </span>
                    </td>
                    <td className="text-right">
                      <span className="font-mono text-xs text-text-muted">{formatCost(jd.estimated_cost_usd ?? 0)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showForm && (
        <JDFormModal onCloseAction={() => setShowForm(false)} onSuccessAction={() => { setShowForm(false); mutate(); }} />
      )}
    </div>
  );
}