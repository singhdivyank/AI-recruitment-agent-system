"use client";
import { useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { listJDs } from "@/lib/api";
import { Topbar } from "@/components/layout/Topbar";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Users, Search, MapPin, Briefcase } from "lucide-react";

export default function CandidatesPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { data } = useSWR("jds-cands", () => listJDs(), { refreshInterval: 10000 });

  const jds = data?.items ?? [];
  const totalCandidates = jds.reduce((s, j) => s + (j.total_candidates ?? 0), 0);
  const totalShortlisted = jds.reduce((s, j) => s + (j.shortlisted_count ?? 0), 0);

  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow="Talent Pool"
        title="Candidates"
        subtitle={`${totalCandidates.toLocaleString()} total · ${totalShortlisted} shortlisted`}
        actions={
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-faint" />
            <input className="field-input pl-7 py-1.5 text-xs w-48" placeholder="Search candidates…"
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        }
      />

      <div className="p-6">
        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: "Total Sourced", value: totalCandidates.toLocaleString(), color: "text-primary" },
            { label: "Shortlisted", value: totalShortlisted, color: "text-success" },
            { label: "Across JDs", value: jds.length, color: "text-warning" },
          ].map(({ label, value, color }) => (
            <div key={label} className="metric-card">
              <div className="section-eyebrow mb-2">{label}</div>
              <div className={`font-mono text-2xl font-semibold ${color}`}>{value}</div>
            </div>
          ))}
        </div>

        {/* JD-grouped candidate summary */}
        <div className="space-y-4">
          {jds.filter(j => j.total_candidates > 0).map(jd => (
            <div key={jd.jd_id} className="bg-card border border-border rounded-xl overflow-hidden">
              <div
                className="flex items-center justify-between px-5 py-3 border-b border-border cursor-pointer hover:bg-card/80"
                onClick={() => router.push(`/jobs/${jd.jd_id}`)}
              >
                <div>
                  <span className="font-display font-semibold text-sm text-text">{jd.title}</span>
                  <div className="flex items-center gap-3 mt-0.5 text-[11px] text-text-muted font-mono">
                    <span className="flex items-center gap-1"><MapPin size={9} />{jd.location}</span>
                    <span className="flex items-center gap-1"><Briefcase size={9} />{jd.employment_type}</span>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="font-mono text-xs text-text-muted">{jd.total_candidates} retrieved</div>
                    <div className="font-mono text-xs text-success">{jd.shortlisted_count} shortlisted</div>
                  </div>
                  <StatusBadge status={jd.status} />
                </div>
              </div>

              {/* Skills preview */}
              <div className="px-5 py-3 flex items-center gap-3">
                <span className="text-[10px] text-text-faint font-mono">Required:</span>
                <div className="flex flex-wrap gap-1">
                  {(jd.must_have_skills ?? []).map(s => (
                    <span key={s} className="text-[9px] font-mono bg-primary/10 text-primary border border-primary/20 px-1.5 py-0.5 rounded">{s}</span>
                  ))}
                </div>
                <div className="ml-auto text-[10px] font-mono text-primary hover:underline cursor-pointer"
                  onClick={() => router.push(`/jobs/${jd.jd_id}`)}>
                  View shortlist →
                </div>
              </div>
            </div>
          ))}

          {jds.filter(j => j.total_candidates > 0).length === 0 && (
            <div className="flex flex-col items-center py-20 text-center">
              <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4">
                <Users size={20} className="text-primary" />
              </div>
              <p className="font-display font-semibold text-text mb-1">No candidates yet</p>
              <p className="text-xs text-text-muted">Submit a Job Description to start sourcing candidates.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}