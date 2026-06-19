"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import {
  getJD, getShortlist, getAuditLog, closeJD,
  sendConversationMessage, getConversation,
} from "@/lib/api";
import { Topbar } from "@/components/layout/Topbar";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { CandidateCard } from "@/components/candidates/CandidateCard";
import { formatCost, formatTokens, PIPELINE_STAGES } from "@/lib/utils";
import {
  ArrowLeft, CheckCircle2, Circle, Loader2, AlertCircle,
  MessageSquare, Clock, FileText, ShieldCheck, Send,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STAGE_DESCRIPTIONS: Record<string, string> = {
  OPEN:        "JD received, initiating compliance check",
  SOURCING:    "Retrieving candidates from LinkedIn, Naukri & ATS",
  SCREENING:   "LLM evaluating candidates against criteria",
  SHORTLISTED: "Ranking complete — candidates ready for review",
  CLOSED:      "Role filled",
};

function WorkflowProgress({ status }: { status: string }) {
  const currentIdx = PIPELINE_STAGES.indexOf(status as any);
  const failed = status === "REJECTED";

  return (
    <div className="space-y-2">
      {PIPELINE_STAGES.map((stage, i) => {
        const done   = !failed && currentIdx > i;
        const active = !failed && currentIdx === i;

        return (
          <div key={stage} className={cn(
            "flex items-center gap-3 py-2 px-3 rounded-lg border transition-colors",
            done   ? "border-success/20 bg-success/5" :
            active ? "border-primary/30 bg-primary/5" :
                     "border-transparent"
          )}>
            <div className="shrink-0">
              {done   ? <CheckCircle2 size={14} className="text-success" /> :
               active ? <Loader2     size={14} className="text-primary animate-spin" /> :
                        <Circle      size={14} className="text-text-faint" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className={cn("text-xs font-semibold", done ? "text-success" : active ? "text-text" : "text-text-faint")}>
                {stage}
              </div>
              {(done || active) && (
                <div className="text-[10px] text-text-muted font-mono mt-0.5 truncate">
                  {STAGE_DESCRIPTIONS[stage]}
                </div>
              )}
            </div>
            {done   && <span className="text-[9px] font-mono text-success shrink-0">Complete</span>}
            {active && <span className="text-[9px] font-mono text-primary shrink-0 animate-pulse">Running</span>}
          </div>
        );
      })}
      {failed && (
        <div className="flex items-center gap-3 py-2 px-3 rounded-lg border border-error/30 bg-error/5">
          <AlertCircle size={14} className="text-error shrink-0" />
          <div className="text-xs font-semibold text-error">Compliance Hold</div>
        </div>
      )}
    </div>
  );
}

export default function JDDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const { data: jd, isLoading, mutate: mutateJD } = useSWR(
    id ? `jd-${id}` : null, () => getJD(id), { refreshInterval: 4000 }
  );
  const { data: shortlistData, mutate: mutateShortlist } = useSWR(
    id && ["SHORTLISTED","CLOSED"].includes(jd?.status ?? "") ? `shortlist-${id}` : null,
    () => getShortlist(id)
  );
  const { data: chatData, mutate: mutateChat } = useSWR(
    id ? `chat-${id}` : null, () => getConversation(id), { refreshInterval: 5000 }
  );
  const { data: auditData } = useSWR(
    id ? `audit-${id}` : null, () => getAuditLog(id), { refreshInterval: 10000 }
  );

  if (isLoading) return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <Loader2 size={24} className="text-primary animate-spin" />
    </div>
  );
  if (!jd) return (
    <div className="min-h-screen bg-bg flex items-center justify-center text-error text-sm">
      Job description not found.
    </div>
  );

  const shortlist = shortlistData?.shortlist ?? [];
  const auditLog  = auditData?.audit_log ?? [];
  const topPick   = shortlist[0];

  const sendChat = async () => {
    if (!chatInput.trim()) return;
    setChatLoading(true);
    try { await sendConversationMessage(id, chatInput); setChatInput(""); mutateChat(); }
    catch {}
    finally { setChatLoading(false); }
  };

  const handleClose = async (candidateId: string, name: string) => {
    if (!confirm(`Close this role and select ${name}?`)) return;
    try {
      await closeJD(id, { jd_id: id, selected_candidate_id: candidateId, recruiter_id: "recruiter-1", notes: "Selected via UI" });
      await mutateShortlist(); await mutateJD();
    } catch { alert("Failed to close JD"); }
  };

  const flattenCandidate = (rc: any) => ({
    ...rc.candidate, final_rank: rc.rank, overall_score: rc.final_score,
    screening_data: rc.screening, outreach_draft: rc.outreach_draft,
  });

  return (
    <div className="min-h-screen bg-bg">
      <Topbar
        eyebrow={jd.employment_type + " · " + jd.location}
        title={jd.title}
        actions={
          <div className="flex items-center gap-3">
            <StatusBadge status={jd.status} size="md" />
            <div className="flex items-center gap-3 text-[11px] font-mono text-text-muted border-l border-border pl-3">
              <span>{formatCost(jd.estimated_cost_usd ?? 0)}</span>
              <span>{formatTokens(jd.token_usage ?? 0)} tokens</span>
              <span>{jd.total_candidates ?? 0} candidates</span>
            </div>
            <Link href="/jobs" className="btn-ghost btn-sm flex items-center gap-1">
              <ArrowLeft size={13} /> Back
            </Link>
          </div>
        }
      />

      <div className="p-6 grid grid-cols-3 gap-5">
        {/* ── Left panel ── */}
        <div className="col-span-1 space-y-4">

          {/* Parsed JD */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText size={13} className="text-text-faint" />
              <div className="section-eyebrow">Parsed Job Details</div>
            </div>
            {jd.parsed_data ? (
              <dl className="space-y-3">
                {[
                  ["Seniority",   jd.parsed_data.seniority_level],
                  ["Experience",  `${jd.years_experience?.min}–${jd.years_experience?.max} years`],
                  ["Remote",      jd.parsed_data.remote_ok ? "Yes" : "No"],
                  ["Urgency",     jd.parsed_data.hiring_urgency],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-[9px] font-mono text-text-faint uppercase tracking-widest mb-0.5">{k}</dt>
                    <dd className="text-xs font-medium text-text capitalize">{v}</dd>
                  </div>
                ))}
                <div>
                  <dt className="text-[9px] font-mono text-text-faint uppercase tracking-widest mb-1.5">Required Skills</dt>
                  <dd className="flex flex-wrap gap-1">
                    {(jd.must_have_skills ?? []).map(s => (
                      <span key={s} className="text-[10px] font-mono bg-primary/10 text-primary border border-primary/20 px-1.5 py-0.5 rounded">{s}</span>
                    ))}
                  </dd>
                </div>
                <div>
                  <dt className="text-[9px] font-mono text-text-faint uppercase tracking-widest mb-1.5">Nice to Have</dt>
                  <dd className="flex flex-wrap gap-1">
                    {(jd.nice_to_have_skills ?? []).map(s => (
                      <span key={s} className="text-[10px] font-mono bg-bg border border-border text-text-muted px-1.5 py-0.5 rounded">{s}</span>
                    ))}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-xs text-text-faint">Parsing in progress…</p>
            )}
          </div>

          {/* Compliance */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck size={13} className="text-text-faint" />
              <div className="section-eyebrow">Compliance</div>
            </div>
            {jd.compliance_passed === null ? (
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <Loader2 size={12} className="animate-spin" /> Checking…
              </div>
            ) : jd.compliance_passed ? (
              <div className="flex items-center gap-2 text-sm text-success font-semibold">
                <CheckCircle2 size={14} /> Passed
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-2 text-sm text-error font-semibold mb-2">
                  <AlertCircle size={14} /> Failed
                </div>
                {(jd.compliance_flags ?? []).map((f, i) => (
                  <p key={i} className="text-[10px] font-mono text-error bg-error/10 border border-error/20 px-2 py-1 rounded mb-1">{f}</p>
                ))}
              </div>
            )}
          </div>

          {/* Workflow progress */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Clock size={13} className="text-text-faint" />
              <div className="section-eyebrow">Workflow Progress</div>
            </div>
            <WorkflowProgress status={jd.status} />
          </div>

          {/* Audit trail */}
          {auditLog.length > 0 && (
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="section-eyebrow mb-3">Audit Trail</div>
              <div className="space-y-3">
                {auditLog.map(a => (
                  <div key={a.audit_id} className="relative pl-4 border-l border-border">
                    <div className="absolute left-[-4px] top-1 w-2 h-2 rounded-full bg-border" />
                    <div className="text-xs font-semibold text-text">{a.action}</div>
                    {a.reason && <p className="text-[10px] text-text-muted mt-0.5 line-clamp-2">{a.reason}</p>}
                    <div className="text-[9px] font-mono text-text-faint mt-0.5">
                      {new Date(a.closed_at).toLocaleDateString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Chat */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <MessageSquare size={13} className="text-text-faint" />
              <div className="section-eyebrow">AI Conversation</div>
            </div>
            <div className="space-y-2 max-h-44 overflow-y-auto mb-3">
              {(chatData?.conversation ?? []).length === 0 ? (
                <p className="text-[11px] text-text-faint font-mono">Ask anything about the pipeline or candidates…</p>
              ) : (
                (chatData?.conversation ?? []).map((msg: any, i: number) => (
                  <div key={i} className={cn(
                    "text-[11px] px-3 py-2 rounded-lg font-mono leading-relaxed",
                    msg.role === "user" ? "bg-primary/10 text-primary" : "bg-bg text-text-muted"
                  )}>
                    <span className="font-bold uppercase text-[9px] tracking-widest mr-1.5">
                      {msg.role === "user" ? "You" : "AI"}
                    </span>
                    {msg.content}
                  </div>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <input
                className="field-input flex-1 text-xs py-1.5"
                placeholder="e.g. Show remote-only candidates…"
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && sendChat()}
              />
              <button onClick={sendChat} disabled={chatLoading} className="btn-primary btn-sm px-3">
                {chatLoading ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
              </button>
            </div>
          </div>
        </div>

        {/* ── Right panel ── */}
        <div className="col-span-2">
          {["SHORTLISTED","CLOSED"].includes(jd.status) ? (
            <div>
              {/* Top pick banner */}
              {topPick && jd.status !== "CLOSED" && (
                <div className="bg-gradient-to-r from-primary/10 to-violet-500/10 border border-primary/20 rounded-xl p-5 mb-5">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="section-eyebrow text-primary mb-1.5">Top Pick · Rank #1</div>
                      <h3 className="font-display font-bold text-xl text-text">{topPick.candidate.name}</h3>
                      <p className="text-sm text-text-muted mt-1">
                        {topPick.candidate.experience_years?.toFixed(0)} yrs · {topPick.candidate.location}
                      </p>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-xs text-text-muted font-mono">Match score:</span>
                        <div className="w-32">
                          <ScoreBar score={topPick.final_score} />
                        </div>
                      </div>
                    </div>
                    <button
                      className="btn-primary"
                      onClick={() => handleClose(topPick.candidate.candidate_id, topPick.candidate.name)}
                    >
                      Select & Close Role
                    </button>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display font-semibold text-sm text-text">
                  Shortlisted Candidates
                </h2>
                <span className="font-mono text-xs text-text-muted">{shortlist.length} ranked</span>
              </div>

              <div className="space-y-3">
                {shortlist.map(rc => (
                  <CandidateCard
                    key={rc.candidate.candidate_id}
                    candidate={flattenCandidate(rc)}
                    onSelect={jd.status !== "CLOSED" ? c => handleClose(c.candidate_id, c.name) : undefined}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-card border border-border rounded-xl flex items-center justify-center min-h-80">
              <div className="text-center py-10">
                <div className="w-14 h-14 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4">
                  <Loader2 size={24} className="text-primary animate-spin" />
                </div>
                <div className="font-display font-semibold text-text mb-1">Pipeline Running</div>
                <div className="text-xs text-text-muted">
                  {jd.status === "SOURCING"   && "Retrieving candidates from all sources…"}
                  {jd.status === "SCREENING"  && "AI evaluating candidates against criteria…"}
                  {jd.status === "PROCESSING" && "Processing pipeline steps…"}
                  {jd.status === "OPEN"       && "Initialising agents…"}
                  {jd.status === "REJECTED"   && `Compliance hold: ${(jd.compliance_flags ?? []).join(", ")}`}
                </div>
                {jd.status === "REJECTED" ? null : (
                  <div className="mt-4 font-mono text-[10px] text-text-faint">
                    {jd.total_candidates ?? 0} candidates retrieved · {jd.shortlisted_count ?? 0} shortlisted
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}