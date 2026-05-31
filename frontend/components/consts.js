export function ScoreBar({ score, max = 10 }) {
  const pct = (score / max) * 100;
  const color = pct >= 70 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-gray-600 w-8 text-right">{score?.toFixed(1)}</span>
    </div>
  );
}

export const EMPLOYMENT_TYPES = ["Full-Time", "Part-Time", "Contract", "Freelance", "Internship"];