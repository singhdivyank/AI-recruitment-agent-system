"use client";
import { useState } from "react";
import { X } from "lucide-react";
import { createJD } from "@/lib/api";
import axios from "axios";

const EMPLOYMENT_TYPES = ["Full-Time","Part-Time","Contract","Freelance","Internship"];

interface JDFormModalProps {
  onCloseAction: () => void;
  onSuccessAction: () => void;
}

export function JDFormModal({ onCloseAction, onSuccessAction }: JDFormModalProps) {
  const [form, setForm] = useState({
    title: "", description: "", must_have_skills: "", nice_to_have_skills: "",
    min_years: 2, max_years: 8, location: "", employment_type: "Full-Time",
    target_hiring_date: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      await createJD({
        title: form.title, description: form.description,
        must_have_skills: form.must_have_skills.split(",").map(s => s.trim()).filter(Boolean),
        nice_to_have_skills: form.nice_to_have_skills.split(",").map(s => s.trim()).filter(Boolean),
        years_experience: { min: +form.min_years, max: +form.max_years },
        location: form.location, employment_type: form.employment_type,
        target_hiring_date: form.target_hiring_date,
      });
      onSuccessAction();
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.detail ??
          "Submission failed. Please try again."
        );
      } else {
        setError("Submission failed. Please try again.");
      }
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-surface border border-border rounded-xl w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl animate-slide-up">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="font-display font-semibold text-base text-text">New Job Description</h2>
            <p className="text-xs text-text-muted mt-0.5 font-mono">
              Triggers: Compliance → Sourcing → Screening → Ranking
            </p>
          </div>
          <button onClick={onCloseAction} className="btn-ghost p-1.5 rounded-lg">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="field-label">Job Title *</label>
            <input className="field-input" value={form.title} onChange={set("title")}
              placeholder="e.g. Senior AI Engineer" required />
          </div>

          <div>
            <label className="field-label">Description *</label>
            <textarea className="field-input h-24 resize-none" value={form.description}
              onChange={set("description")} placeholder="Describe the role, responsibilities, and context..."
              required minLength={50} />
          </div>

          <div>
            <label className="field-label">Must-Have Skills * <span className="text-text-faint normal-case tracking-normal">comma-separated</span></label>
            <input className="field-input" value={form.must_have_skills} onChange={set("must_have_skills")}
              placeholder="Python, LangGraph, RAG, FastAPI" required />
          </div>

          <div>
            <label className="field-label">Nice-to-Have Skills <span className="text-text-faint normal-case tracking-normal">comma-separated</span></label>
            <input className="field-input" value={form.nice_to_have_skills} onChange={set("nice_to_have_skills")}
              placeholder="Kubernetes, Pinecone, LangSmith" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="field-label">Min Years</label>
              <input type="number" min={0} className="field-input" value={form.min_years} onChange={set("min_years")} />
            </div>
            <div>
              <label className="field-label">Max Years</label>
              <input type="number" min={0} className="field-input" value={form.max_years} onChange={set("max_years")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="field-label">Location *</label>
              <input className="field-input" value={form.location} onChange={set("location")}
                placeholder="Boston, MA / Remote" required />
            </div>
            <div>
              <label className="field-label">Employment Type</label>
              <select className="field-input" value={form.employment_type} onChange={set("employment_type")}>
                {EMPLOYMENT_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="field-label">Target Hiring Date *</label>
            <input type="date" className="field-input" value={form.target_hiring_date}
              onChange={set("target_hiring_date")} required />
          </div>

          {error && (
            <div className="bg-error/10 border border-error/30 text-error text-xs font-mono px-3 py-2 rounded-lg">
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary w-full py-2.5 text-sm mt-2">
            {loading ? "Launching pipeline…" : "Submit & Start Pipeline →"}
          </button>
        </form>
      </div>
    </div>
  );
}