import { useState } from "react";
import { createJD } from "../../services/api";
import { EMPLOYMENT_TYPES} from "../consts";

export default function JDForm({ onSuccess }) {
  const [form, setForm] = useState({
    title: "",
    description: "",
    must_have_skills: "",
    nice_to_have_skills: "",
    min_years: 2,
    max_years: 8,
    location: "",
    employment_type: "Full-Time",
    target_hiring_date: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await createJD({
        title: form.title,
        description: form.description,
        must_have_skills: form.must_have_skills.split(",").map((s) => s.trim()).filter(Boolean),
        nice_to_have_skills: form.nice_to_have_skills.split(",").map((s) => s.trim()).filter(Boolean),
        years_experience: { min: parseInt(form.min_years), max: parseInt(form.max_years) },
        location: form.location,
        employment_type: form.employment_type,
        target_hiring_date: form.target_hiring_date,
      });
      onSuccess?.();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to submit JD");
    } finally {
      setLoading(false);
    }
  };

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <form onSubmit={handleSubmit} className="p-6 space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Job Title *</label>
        <input
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={form.title}
          onChange={set("title")}
          placeholder="e.g. Senior AI Engineer"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
        <textarea
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 h-28 resize-none"
          value={form.description}
          onChange={set("description")}
          placeholder="Describe the role, responsibilities, and context..."
          required
          minLength={50}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Must-Have Skills * <span className="text-gray-400 font-normal">(comma-separated)</span></label>
        <input
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={form.must_have_skills}
          onChange={set("must_have_skills")}
          placeholder="Python, LangChain, FastAPI, RAG"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Nice-to-Have Skills <span className="text-gray-400 font-normal">(comma-separated)</span></label>
        <input
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={form.nice_to_have_skills}
          onChange={set("nice_to_have_skills")}
          placeholder="Kubernetes, Pinecone, LangSmith"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Min Years Experience</label>
          <input
            type="number"
            min={0}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={form.min_years}
            onChange={set("min_years")}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Max Years Experience</label>
          <input
            type="number"
            min={0}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={form.max_years}
            onChange={set("max_years")}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Location *</label>
          <input
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={form.location}
            onChange={set("location")}
            placeholder="Boston, MA"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Employment Type</label>
          <select
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={form.employment_type}
            onChange={set("employment_type")}
          >
            {EMPLOYMENT_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Target Hiring Date *</label>
        <input
          type="date"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={form.target_hiring_date}
          onChange={set("target_hiring_date")}
          required
        />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
          {error}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary flex-1">
          {loading ? "Submitting..." : "Submit JD & Start Pipeline"}
        </button>
      </div>
    </form>
  );
}
