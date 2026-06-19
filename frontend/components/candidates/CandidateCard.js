import { useState } from "react";
import Link from "next/link";
import StatusBadge from "../dashboard/StatusBadge";
import { ScoreBar } from "../consts";

export default function CandidateCard({ candidate, onSelect }) {
  const [expanded, setExpanded] = useState(false);
  const screening = candidate.screening_data;

  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-500 to-purple-500 flex items-center justify-center text-white font-bold text-sm">
              {(candidate.name || "?")[0].toUpperCase()}
            </div>
            <div>
              <div className="font-semibold text-gray-900">{candidate.name}</div>
              <div className="text-sm text-gray-500">
                {candidate.experience_years?.toFixed(0)} yrs · {candidate.location}
              </div>
            </div>
            {candidate.final_rank && (
              <span className="text-xs font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded">
                #{candidate.final_rank}
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-1 mt-2">
            {(candidate.skills || []).slice(0, 6).map((s) => (
              <span key={s} className="text-xs bg-gray-50 border border-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {s}
              </span>
            ))}
          </div>

          {candidate.overall_score != null && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-gray-500">Overall Score:</span>
              <span className="font-bold text-gray-900">{candidate.overall_score?.toFixed(1)}/10</span>
              <ScoreBar score={candidate.overall_score} />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 ml-4">
          <StatusBadge status={candidate.status} />
          {onSelect && (
            <button onClick={() => onSelect(candidate)} className="btn-primary text-xs py-1">
              Select
            </button>
          )}
          <Link href={`/candidates/${candidate.candidate_id}`} className="btn-secondary text-xs py-1">
            Profile
          </Link>
          <button
            onClick={() => setExpanded((e) => !e)}
            className="btn-secondary text-xs py-1"
          >
            {expanded ? "Less" : "Details"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-4">
          {/* Sources */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Sources</h4>
            <div className="flex gap-2">
              {(candidate.source_profiles || []).map((sp, i) => (
                <span key={i} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                  {sp.source}
                </span>
              ))}
            </div>
          </div>

          {/* Per-criterion scores */}
          {screening?.criterion_scores?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Criterion Scores</h4>
              <div className="space-y-2">
                {screening.criterion_scores.map((cs) => (
                  <div key={cs.criterion}>
                    <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                      <span>{cs.criterion}</span>
                    </div>
                    <ScoreBar score={cs.score} />
                    <p className="text-xs text-gray-400 mt-0.5">{cs.reasoning}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strengths & Gaps */}
          {screening && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-2">Strengths</h4>
                <ul className="space-y-1">
                  {(screening.strengths || []).map((s, i) => (
                    <li key={i} className="text-xs text-gray-600 flex gap-1"><span>✓</span> {s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-2">Gaps</h4>
                <ul className="space-y-1">
                  {(screening.gaps || []).map((g, i) => (
                    <li key={i} className="text-xs text-gray-600 flex gap-1"><span>!</span> {g}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Outreach Draft */}
          {candidate.outreach_draft && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Outreach Draft</h4>
              <pre className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg whitespace-pre-wrap font-sans">
                {candidate.outreach_draft}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
