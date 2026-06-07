import { useRouter } from "next/router";
import useSWR from "swr";
import Link from "next/link";
import { getJD, getShortlist, getAuditLog, closeJD, sendConversationMessage, getConversation } from "../../services/api";
import StatusBadge from "../../components/dashboard/StatusBadge";
import CandidateCard from "../../components/candidates/CandidateCard";

export default function JDDetail() {
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const { id } = router.query;

  const { data: jd, isLoading: jdLoading } = useSWR(
    id ? `jd-${id}` : null,
    () => getJD(id),
    { refreshInterval: 4000 }
  );
  const { data: shortlistData, mutate: mutateShortlist } = useSWR(
    id && jd?.status === "SHORTLISTED" ? `shortlist-${id}` : null,
    () => getShortlist(id)
  );
  const { data: chatData, mutate: mutateChat } = useSWR(
    id ? `chat-${id}` : null,
    () => getConversation(id),
    { refreshInterval: 5000 }
  );
  const { data: auditData } = useSWR(
    id ? `audit-${id}` : null,
    () => getAuditLog(id),
    { refreshInterval: 10000 }
  );

  if (jdLoading) return <div className="p-8 text-center text-gray-400">Loading...</div>;
  if (!jd) return <div className="p-8 text-center text-red-400">JD not found</div>;

  const shortlist = shortlistData?.shortlist || [];
  const auditLog = auditData?.audit_log || [];

  const sendChat = async () => {
    if (!chatInput.trim()) return;
    setChatLoading(true);
    try {
      await sendConversationMessage(id, chatInput);
      setChatInput("");
      mutateChat();
    } catch {}
    finally { setChatLoading(false); }
  };

  const handleClose = async (candidateId, candidateName) => {
    if (!confirm(`Close JD and select ${candidateName}?`)) return;
    try {
      await closeJD(id, {
        jd_id: id,
        selected_candidate_id: candidateId,
        recruiter_id: "recruiter-1",
        notes: "Selected via UI",
      });
      mutateShortlist();
      router.reload();
    } catch (e) {
      alert("Failed to close JD");
    }
  };

  const topPick = shortlist[0];

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link href="/" className="text-gray-400 hover:text-gray-600">← Back</Link>
          <div className="flex-1">
            <h1 className="text-lg font-bold">{jd.title}</h1>
            <div className="flex items-center gap-3 mt-0.5">
              <StatusBadge status={jd.status} />
              <span className="text-sm text-gray-400">{jd.location} · {jd.employment_type}</span>
              <span className="text-sm text-gray-400">{jd.total_candidates} candidates · {jd.shortlisted_count} shortlisted</span>
            </div>
          </div>
          <div className="text-right text-sm text-gray-500">
            <div>Cost: <span className="font-mono font-semibold">${(jd.estimated_cost_usd || 0).toFixed(4)}</span></div>
            <div>Tokens: {((jd.token_usage || 0) / 1000).toFixed(1)}k</div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-3 gap-6">
        {/* Left: JD Details */}
        <div className="col-span-1 space-y-4">
          <div className="card">
            <h3 className="font-semibold mb-3">Parsed JD</h3>
            {jd.parsed_data ? (
              <dl className="space-y-2 text-sm">
                <div><dt className="text-gray-500">Seniority</dt><dd className="font-medium">{jd.parsed_data.seniority_level}</dd></div>
                <div><dt className="text-gray-500">YOE</dt><dd className="font-medium">{jd.years_experience?.min}–{jd.years_experience?.max} years</dd></div>
                <div><dt className="text-gray-500">Remote OK</dt><dd className="font-medium">{jd.parsed_data.remote_ok ? "Yes" : "No"}</dd></div>
                <div><dt className="text-gray-500">Urgency</dt><dd className="font-medium capitalize">{jd.parsed_data.hiring_urgency}</dd></div>
                <div>
                  <dt className="text-gray-500 mb-1">Must-Have Skills</dt>
                  <dd className="flex flex-wrap gap-1">
                    {(jd.must_have_skills || []).map((s) => (
                      <span key={s} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{s}</span>
                    ))}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500 mb-1">Nice to Have</dt>
                  <dd className="flex flex-wrap gap-1">
                    {(jd.nice_to_have_skills || []).map((s) => (
                      <span key={s} className="text-xs bg-gray-50 text-gray-600 px-2 py-0.5 rounded">{s}</span>
                    ))}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-gray-400">Parsing in progress...</p>
            )}
          </div>

          {/* Compliance */}
          <div className="card">
            <h3 className="font-semibold mb-2">Compliance</h3>
            {jd.compliance_passed === null ? (
              <p className="text-sm text-gray-400">Checking...</p>
            ) : jd.compliance_passed ? (
              <div className="flex items-center gap-2 text-green-600 text-sm font-medium">
                <span>✅</span> Passed
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-2 text-red-600 text-sm font-medium mb-2">
                  <span>❌</span> Failed
                </div>
                {(jd.compliance_flags || []).map((f, i) => (
                  <p key={i} className="text-xs text-red-500 bg-red-50 px-2 py-1 rounded mb-1">{f}</p>
                ))}
              </div>
            )}
          </div>

          {/* Audit Log */}
          <div className="card">
            <h3 className="font-semibold mb-3">Audit Trail</h3>
            {auditLog.length === 0 ? (
              <p className="text-sm text-gray-400">No events yet</p>
            ) : (
              <div className="space-y-2">
                {auditLog.map((a) => (
                  <div key={a.audit_id} className="text-xs">
                    <div className="flex justify-between text-gray-500">
                      <span className="font-medium text-gray-700">{a.action}</span>
                      <span>{new Date(a.closed_at).toLocaleDateString()}</span>
                    </div>
                    {a.reason && <p className="text-gray-500 mt-0.5 line-clamp-2">{a.reason}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Conversation / Refinement */}
          <div className="card">
            <h3 className="font-semibold mb-3">AI Conversation</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto mb-3">
              {(chatData?.conversation || []).map((msg, i) => (
                <div key={i} className={`text-xs p-2 rounded ${msg.role === "user" ? "bg-blue-50 text-blue-800" : "bg-gray-50 text-gray-700"}`}>
                  <span className="font-semibold uppercase mr-1">{msg.role}:</span>{msg.content}
                </div>
              ))}
              {(chatData?.conversation || []).length === 0 && (
                <p className="text-xs text-gray-400">Ask a question about the candidates...</p>
              )}
            </div>
            <div className="flex gap-2">
              <input
                className="flex-1 border border-gray-200 rounded px-2 py-1 text-xs"
                placeholder="e.g. Show me only remote candidates"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendChat()}
              />
              <button onClick={sendChat} disabled={chatLoading} className="btn-primary text-xs py-1 px-3">
                {chatLoading ? "..." : "Send"}
              </button>
            </div>
          </div>
        </div>

        {/* Right: Shortlist */}
        <div className="col-span-2">
          {jd.status === "SHORTLISTED" || jd.status === "CLOSED" ? (
            <div>
              {/* Top Pick Banner */}
              {topPick && jd.status !== "CLOSED" && (
                <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-xl p-4 mb-6">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-xs font-semibold text-purple-600 uppercase tracking-wide mb-1">⭐ Top Pick</div>
                      <div className="text-lg font-bold">{topPick.name}</div>
                      <div className="text-sm text-gray-600">{topPick.experience_years?.toFixed(0)} years · {topPick.location} · Score: <strong>{topPick.overall_score?.toFixed(1)}/10</strong></div>
                    </div>
                    <button
                      onClick={() => handleClose(topPick.candidate_id, topPick.name)}
                      className="btn-primary"
                    >
                      Select & Close JD
                    </button>
                  </div>
                </div>
              )}

              <h2 className="text-lg font-semibold mb-4">
                Shortlisted Candidates ({shortlist.length})
              </h2>
              <div className="space-y-4">
                {shortlist.map((c) => (
                  <CandidateCard
                    key={c.candidate_id}
                    candidate={c}
                    jdId={id}
                    onSelect={jd.status !== "CLOSED" ? () => handleClose(c.candidate_id, c.name) : null}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="card h-full flex items-center justify-center text-center py-20">
              <div>
                <div className="text-5xl mb-4">
                  {jd.status === "SOURCING" ? "🔍" :
                   jd.status === "SCREENING" ? "📊" :
                   jd.status === "REJECTED" ? "🚫" : "⏳"}
                </div>
                <div className="text-lg font-semibold text-gray-600 mb-1">
                  {jd.status === "REJECTED" ? "JD Rejected" : "Pipeline Running"}
                </div>
                <div className="text-sm text-gray-400">
                  {jd.status === "SOURCING" && "Searching LinkedIn, Naukri, and ATS..."}
                  {jd.status === "SCREENING" && "Screening candidates with AI..."}
                  {jd.status === "OPEN" && "Starting pipeline..."}
                  {jd.status === "PROCESSING" && "Processing..."}
                  {jd.status === "REJECTED" && `Compliance flags: ${(jd.compliance_flags || []).join(", ")}`}
                </div>
                {!["REJECTED", "CLOSED"].includes(jd.status) && (
                  <div className="mt-4 flex justify-center">
                    <div className="animate-spin h-6 w-6 border-2 border-brand-500 border-t-transparent rounded-full"></div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}