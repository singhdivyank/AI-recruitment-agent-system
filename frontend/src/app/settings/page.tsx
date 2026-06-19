import { Topbar } from "@/components/layout/Topbar";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-bg">
      <Topbar eyebrow="Configuration" title="Settings" subtitle="Platform configuration and API keys" />
      <div className="p-6">
        <div className="bg-card border border-border rounded-xl p-8 flex flex-col items-center text-center">
          <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4">
            <Settings size={20} className="text-primary" />
          </div>
          <p className="font-display font-semibold text-text mb-1">Settings</p>
          <p className="text-xs text-text-muted">Configuration panel — coming soon.</p>
        </div>
      </div>
    </div>
  );
}