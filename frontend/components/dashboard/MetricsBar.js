// MetricsBar component
export function MetricsBar({ cost, jdCounts }) {
  const pct = Math.min(cost?.budget_used_pct || 0, 100);
  return (
    <div className="card mb-6 flex items-center gap-8">
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-wide">Daily LLM Cost</div>
        <div className="text-xl font-bold text-gray-900">${cost?.daily_cost_usd?.toFixed(4)}</div>
      </div>
      <div className="flex-1">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Budget Usage</span>
          <span>{pct.toFixed(1)}% of ${cost?.daily_budget_usd}</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${pct > 80 ? "bg-red-500" : pct > 50 ? "bg-yellow-500" : "bg-green-500"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <div className="text-center">
        <div className="text-xs text-gray-500">Active JDs</div>
        <div className="font-bold text-lg">{jdCounts.open}</div>
      </div>
      <div className="text-center">
        <div className="text-xs text-gray-500">Closed</div>
        <div className="font-bold text-lg">{jdCounts.closed}</div>
      </div>
    </div>
  );
}

export default MetricsBar;
