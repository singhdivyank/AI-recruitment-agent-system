"use client";
import { useState } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp, ExternalLink, MapPin, Briefcase } from "lucide-react";
import type { Candidate } from "@/types";
import type { CriterionScore, ScreeningData } from "@/types";

interface CandidateCardProps {
  candidate: Candidate & {
    final_rank?: number;
    overall_score?: number;
    screening_data?: ScreeningData;
    outreach_draft?: string;
  };
  onSelect?: (c: CandidateCardProps["candidate"]) => void;
}

export function CandidateCard({ candidate, onSelect }: CandidateCardProps) {
  const [expanded, setExpanded] = useState(false);
  const screening = candidate.screening_data;
  const initials = (candidate.name || "?").split(" ").map((p: string) => p[0]).join("").slice(0, 2).toUpperCase();
  const criterionScores = screening?.criterion_scores ?? [];

  return (
    <div className={cn(
      "bg-card border rounded-xl transition-all duration-200",
      expanded ? "border-primary/30" : "border-border hover:border-border/80"
    )}>
      {/* Header */}
      <div className="p-4 flex items-start gap-3">
        {/* Avatar */}
        <div className="w-9 h-9 rounded-lg bg-primary-gradient flex items-center justify-center font-display font-bold text-sm text-white shrink-0">
          {initials}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-display font-semibold text-sm text-text">{candidate.name}</span>
            {candidate.final_rank && (
              <span className="font-mono text-[9px] font-bold bg-primary/10 text-primary border border-primary/20 px-1.5 py-0.5 rounded">
                #{candidate.final_rank}
              </span>
            )}
            <StatusBadge status={candidate.status} />
          </div>
          <div className="flex items-center gap-3 mt-1 text-[11px] text-text-muted font-mono">
            <span className="flex items-center gap-1"><Briefcase size={9} />{candidate.experience_years?.toFixed(0)} yrs</span>
            <span className="flex items-center gap-1"><MapPin size={9} />{candidate.location}</span>
          </div>

          {/* Skills */}
          <div className="flex flex-wrap gap-1 mt-2">
            {(candidate.skills ?? []).slice(0, 5).map(s => (
              <span key={s} className="text-[9px] font-mono border border-border bg-bg text-text-muted px-1.5 py-0.5 rounded">
                {s}
              </span>
            ))}
          </div>

          {/* Overall score */}
          {candidate.overall_score != null && (
            <div className="flex items-center gap-2 mt-2.5">
              <span className="text-[10px] text-text-faint font-mono">Match</span>
              <div className="w-32">
                <ScoreBar score={candidate.overall_score} />
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-1.5 shrink-0">
          {onSelect && (
            <button onClick={() => onSelect(candidate)} className="btn-primary btn-sm text-xs">
              Select
            </button>
          )}
          <Link href={`/candidates/${candidate.candidate_id}`} className="btn-outline btn-sm text-xs flex items-center gap-1">
            Profile <ExternalLink size={10} />
          </Link>
          <button onClick={() => setExpanded(e => !e)} className="btn-ghost btn-sm text-xs flex items-center gap-1">
            {expanded ? <><ChevronUp size={11} /> Less</> : <><ChevronDown size={11} /> Details</>}
          </button>
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-border p-4 space-y-4 animate-fade-in">
          {/* Sources */}
          {(candidate.source_profiles ?? []).length > 0 && (
            <div>
              <div className="section-eyebrow mb-2">Sources</div>
              <div className="flex gap-2">
                {candidate.source_profiles!.map((sp, i) => (
                  <span key={i} className="text-[10px] font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded">
                    {sp.source}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Criterion scores */}
          {criterionScores.length > 0 && (
            <div>
              <div className="section-eyebrow mb-2">Criterion Scores</div>
              <div className="space-y-2.5">
                {criterionScores.map((cs: CriterionScore) => (
                  <div key={cs.criterion}>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-text-muted font-mono min-w-[130px] truncate">{cs.criterion}</span>
                      <ScoreBar score={cs.score} />
                    </div>
                    {cs.reasoning && (
                      <p className="text-[10px] text-text-faint mt-0.5 ml-[142px] font-mono leading-relaxed">{cs.reasoning}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strengths & Gaps */}
          {screening && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="section-eyebrow text-success mb-2">Strengths</div>
                <ul className="space-y-1.5">
                  {(screening.strengths ?? []).map((s: string, i: number) => (
                    <li key={i} className="text-xs text-text-muted flex gap-2">
                      <span className="text-success font-bold mt-0.5">✓</span>{s}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="section-eyebrow text-error mb-2">Gaps</div>
                <ul className="space-y-1.5">
                  {(screening.gaps ?? []).map((g: string, i: number) => (
                    <li key={i} className="text-xs text-text-muted flex gap-2">
                      <span className="text-error font-bold mt-0.5">!</span>{g}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* AI reasoning */}
          {screening?.overall_reasoning && (
            <div>
              <div className="section-eyebrow mb-2">Why This Candidate?</div>
              <p className="text-xs text-text-muted bg-bg border border-border rounded-lg p-3 font-mono leading-relaxed">
                {screening.overall_reasoning}
              </p>
            </div>
          )}

          {/* Outreach draft */}
          {candidate.outreach_draft && (
            <div>
              <div className="section-eyebrow mb-2">Outreach Draft</div>
              <pre className="text-xs text-text-muted bg-bg border border-border rounded-lg p-3 font-mono whitespace-pre-wrap leading-relaxed">
                {candidate.outreach_draft}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}