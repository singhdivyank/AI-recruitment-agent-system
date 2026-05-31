// StatusBadge component
export default function StatusBadge({ status }) {
  const cls = {
    OPEN: "status-open",
    SOURCING: "status-sourcing",
    SCREENING: "status-screening",
    SHORTLISTED: "status-shortlisted",
    CLOSED: "status-closed",
    REJECTED: "status-rejected",
    PROCESSING: "status-processing",
    NORMALIZED: "badge bg-cyan-100 text-cyan-800",
    SCREENED: "status-screening",
    SELECTED: "status-closed",
    SOURCED: "badge bg-blue-50 text-blue-600",
  }[status] || "badge bg-gray-100 text-gray-500";

  return <span className={cls}>{status}</span>;
}
