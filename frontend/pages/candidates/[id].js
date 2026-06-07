import { useState } from "react";
import { useRouter } from "next/router";
import useSWR from "swr";
import Link from "next/link";
import { getCandidate } from "../../services/api";
import StatusBadge from "../../components/dashboard/StatusBadge";
import axios from "axios";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function ScoreBar({ score, max = 10, overridden = false }) {
  const pct = Math.min((score / max) * 100, 100);
  const color = pct >= 70 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} ${overridden ? "opacity-70 border-2 border-dashed" : ""}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-mono w-10 text-right ${overridden ? "text-purple-600 font-bold" : "text-gray-600"}`}>
        {score?.toFixed(1)}{overridden ? "✎" : ""}
      </span>
    </div>
  );
}

export default function CandidatePage() {
  const router = useRouter();
  const { id } = router.query;
  const { data: candidate, mutate } = useSWR(id ? `candidate-${id}` : null, () => getCandidate(id));
  const [overrides, setOverrides] = useState({});
  const [notes, setNotes] = useState("");
  const [decision, setDecision] = useState("");
  const [saving, setSaving] = useState(false);
  const [outreachMsg, setOutreachMsg] = useState({ subject: "", body: "" });
  const [sendingOutreach, setSendingOutreach] = useState(false);

  if (!candidate) return <div className="p-8 text-center text-gray-400">Loading...</div>;

  const screening = candidate.screening_data;
  const criterionScores = screening?.criterion_scores || [];

  const handleOverrideChange = (criterion, value) => {
    setOverrides((prev) => ({ ...prev, [criterion]: parseFloat(value) }));
  };

  const saveOverrides = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/api/v1/jds/${candidate.jd_id}/candidates/${id}/override`, {
        recruiter_id: "recruiter-1",
        score_overrides: overrides,
        notes,
        decision: decision || null,
      });
      await mutate();
      alert("Overrides saved.");
    } catch {
      alert("Failed to save overrides.");
    } finally {
      setSaving(false);
    }
  };

  const sendOutreach = async () => {
    setSendingOutreach(true);
    try {
      await axios.post(`${API}/api/v1/candidates/${id}/outreach`, {
        recruiter_id: "recruiter-1",
        subject: outreachMsg.subject,
        body: outreachMsg.body,
        channel: "email",
      });
      await mutate();
      alert("Outreach recorded as sent.");
    } catch {
      alert("Failed to record outreach.");
    } finally {
      setSendingOutreach(false);
    }
  };

  // Pre-fill outreach from draft
  const prefillOutreach = () => {
    if (candidate.outreach_draft) {
      const lines = candidate.outreach_draft.split("\n");
      const subjectLine = lines.find((l) => l.startsWith("Subject:"));
      const subject = subjectLine ? subjectLine.replace("Subject: ", "") : `Opportunity for ${candidate.name}`;
      const body = lines.filter((l) => !l.startsWith("Subject:")).join("\n").trim();
      setOutreachMsg({ subject, body });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link href={`/jd/${candidate.jd_id}`} className="text-gray-400 hover:text-gray-600">← Back to JD</Link>
          <div className="flex-1 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold">
              {(candidate.name || "?")[0].toUpperCase()}
            </div>
            <div>
              <h1 className="text-lg font-bold">{candidate.name}</h1>
              <p className="text-sm text-gray-500">{candidate.experience_years?.toFixed(0)} yrs · {candidate.location}</p>
            </div>
            {candidate.final_rank && (
              <span className="text-sm font-bold text-purple-700 bg-purple-50 px-3 py-1 rounded-full">
                Rank #{candidate.final_rank}
              </span>
            )}
            <StatusBadge status={candidate.status} />
          </div>
          {candidate.overall_score != null && (
            <div className="text-right">
              <div className="text-2xl font-bold text-gray-900">{candidate.overall_score?.toFixed(1)}<span className="text-sm text-gray-400">/10</span></div>
              <div className="text-xs text-gray-400">Overall Score</div>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-3 gap-6">

        {/* Left col: Profile */}
        <div className="col-span-1 space-y-4">
          <div className="card">
            <h3 className="font-semibold mb-3">Profile</h3>
            <dl className="space-y-2 text-sm">
              {candidate.email && <div><dt className="text-gray-500">Email</dt><dd>{candidate.email}</dd></div>}
              {candidate.phone && <div><dt className="text-gray-500">Phone</dt><dd>{candidate.phone}</dd></div>}
              {candidate.location && <div><dt className="text-gray-500">Location</dt><dd>{candidate.location}</dd></div>}
              <div><dt className="text-gray-500">Experience</dt><dd className="font-medium">{candidate.experience_years?.toFixed(1)} years</dd></div>
            </dl>
            <div className="flex gap-2 mt-3">
              {candidate.linkedin_url && (
                <a href={candidate.linkedin_url} target="_blank" className="text-xs text-blue-600 hover:underline">LinkedIn ↗</a>
              )}
              {candidate.github_url && (
                <a href={candidate.github_url} target="_blank" className="text-xs text-gray-600 hover:underline">GitHub ↗</a>
              )}
            </div>
          </div>

          {/* Sources */}
          <div className="card">
            <h3 className="font-semibold mb-3">Source Profiles</h3>
            {(candidate.source_profiles || []).map((sp, i) => (
              <div key={i} className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{sp.source}</span>
                {sp.url && <a href={sp.url} target="_blank" className="text-xs text-gray-500 hover:text-blue-600 truncate">View profile ↗</a>}
              </div>
            ))}
          </div>

          {/* Skills */}
          <div className="card">
            <h3 className="font-semibold mb-3">Skills</h3>
            <div className="flex flex-wrap gap-1.5">
              {(candidate.skills || []).map((s) => (
                <span key={s} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">{s}</span>
              ))}
            </div>
          </div>

          {/* Employment */}
          <div className="card">
            <h3 className="font-semibold mb-3">Employment History</h3>
            <div className="space-y-3">
              {(candidate.employment_history || []).slice(0, 5).map((e, i) => (
                <div key={i} className="text-sm">
                  <div className="font-medium">{e.title}</div>
                  <div className="text-gray-500">{e.company} · {e.start_date}–{e.end_date || "Present"}</div>
                  {e.description && <p className="text-gray-500 text-xs mt-0.5 line-clamp-2">{e.description}</p>}
                </div>
              ))}
            </div>
          </div>

          {/* Education */}
          <div className="card">
            <h3 className="font-semibold mb-3">Education</h3>
            {(candidate.education || []).map((e, i) => (
              <div key={i} className="text-sm mb-2">
                <div className="font-medium">{e.degree} in {e.field_of_study}</div>
                <div className="text-gray-500">{e.institution}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Middle col: Screening + HITL Overrides */}
        <div className="col-span-1 space-y-4">
          <div className="card">
            <h3 className="font-semibold mb-3">Per-Criterion Scores</h3>
            {criterionScores.length === 0 ? (
              <p className="text-sm text-gray-400">No screening data yet.</p>
            ) : (
              <div className="space-y-4">
                {criterionScores.map((cs) => (
                  <div key={cs.criterion}>
                    <div className="flex justify-between text-xs text-gray-600 mb-1">
                      <span className="font-medium">{cs.criterion}</span>
                      <span className="text-gray-400">weight: {cs.weight}×</span>
                    </div>
                    <ScoreBar
                      score={overrides[cs.criterion] ?? cs.score}
                      overridden={cs.criterion in overrides}
                    />
                    <p className="text-xs text-gray-500 mt-1">{cs.reasoning}</p>
                    {cs.evidence && <p className="text-xs text-blue-500 mt-0.5 italic">"{cs.evidence}"</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Strengths & Gaps */}
          {screening && (
            <div className="card">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-2">Strengths</h4>
                  <ul className="space-y-1">
                    {(screening.strengths || []).map((s, i) => (
                      <li key={i} className="text-xs text-gray-600 flex gap-1"><span className="text-green-500">✓</span>{s}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-2">Gaps</h4>
                  <ul className="space-y-1">
                    {(screening.gaps || []).map((g, i) => (
                      <li key={i} className="text-xs text-gray-600 flex gap-1"><span className="text-red-400">!</span>{g}</li>
                    ))}
                  </ul>
                </div>
              </div>
              {screening.screening_summary && (
                <p className="text-xs text-gray-500 mt-3 pt-3 border-t border-gray-100">{screening.screening_summary}</p>
              )}
            </div>
          )}

          {/* HITL Override Panel */}
          <div className="card border-l-4 border-purple-400">
            <h3 className="font-semibold mb-3 text-purple-700">✎ Override Scores</h3>
            <p className="text-xs text-gray-500 mb-3">Adjust AI scores before re-ranking. Overridden scores affect the final ranking formula.</p>
            <div className="space-y-3">
              {criterionScores.slice(0, 6).map((cs) => (
                <div key={cs.criterion} className="flex items-center gap-2">
                  <label className="text-xs text-gray-600 w-32 truncate">{cs.criterion}</label>
                  <input
                    type="range" min="0" max="10" step="0.5"
                    value={overrides[cs.criterion] ?? cs.score}
                    onChange={(e) => handleOverrideChange(cs.criterion, e.target.value)}
                    className="flex-1"
                  />
                  <span className="text-xs font-mono w-8 text-right text-purple-700">
                    {(overrides[cs.criterion] ?? cs.score).toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-4 space-y-2">
              <textarea
                className="w-full border border-gray-200 rounded px-2 py-1 text-xs resize-none h-16"
                placeholder="Recruiter notes..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <select
                className="w-full border border-gray-200 rounded px-2 py-1 text-xs"
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
              >
                <option value="">-- Decision --</option>
                <option value="APPROVE">✅ Approve for shortlist</option>
                <option value="HOLD">⏸ Hold</option>
                <option value="REJECT">❌ Reject</option>
              </select>
              <button onClick={saveOverrides} disabled={saving} className="btn-primary w-full text-sm">
                {saving ? "Saving..." : "Save Overrides"}
              </button>
            </div>
          </div>
        </div>

        {/* Right col: Outreach */}
        <div className="col-span-1 space-y-4">
          <div className="card">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold">Outreach Draft</h3>
              <button onClick={prefillOutreach} className="btn-secondary text-xs py-1">Load AI Draft</button>
            </div>
            <div className="space-y-2">
              <input
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm"
                placeholder="Subject line..."
                value={outreachMsg.subject}
                onChange={(e) => setOutreachMsg((m) => ({ ...m, subject: e.target.value }))}
              />
              <textarea
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm h-48 resize-none"
                placeholder="Message body..."
                value={outreachMsg.body}
                onChange={(e) => setOutreachMsg((m) => ({ ...m, body: e.target.value }))}
              />
              <button onClick={sendOutreach} disabled={sendingOutreach || !outreachMsg.subject} className="btn-primary w-full">
                {sendingOutreach ? "Sending..." : "Mark as Sent"}
              </button>
            </div>
          </div>

          {/* Recruiter notes display */}
          {candidate.recruiter_notes && (
            <div className="card border-l-4 border-yellow-400">
              <h3 className="text-sm font-semibold text-yellow-700 mb-2">Recruiter Notes</h3>
              <p className="text-sm text-gray-600">{candidate.recruiter_notes}</p>
            </div>
          )}

          {/* Score breakdown if ranked */}
          {candidate.screening_data?.criterion_scores && (
            <div className="card">
              <h3 className="font-semibold mb-3">Score Breakdown</h3>
              <div className="space-y-2">
                {[
                  { label: "Skill Match (40%)", key: "skill_match" },
                  { label: "Experience (20%)", key: "experience_score" },
                  { label: "Semantic Sim (20%)", key: "semantic_similarity" },
                  { label: "Location Fit (10%)", key: "location_fit" },
                  { label: "Recruiter Pref (10%)", key: "recruiter_preference" },
                ].map((item) => (
                  <div key={item.key} className="text-xs">
                    <div className="flex justify-between text-gray-500 mb-0.5">
                      <span>{item.label}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-gray-100 flex justify-between">
                <span className="text-sm font-semibold">Final Score</span>
                <span className="text-lg font-bold text-gray-900">{candidate.overall_score?.toFixed(2)}/10</span>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}