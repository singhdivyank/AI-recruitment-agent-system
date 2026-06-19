"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Briefcase, Users, GitBranch,
  BarChart3, Activity, Plug, Settings, Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/",              label: "Dashboard",     icon: LayoutDashboard },
  { href: "/jobs",          label: "Job Descriptions", icon: Briefcase },
  { href: "/candidates",    label: "Candidates",    icon: Users },
  { href: "/workflows",     label: "Agent Workflows", icon: GitBranch },
  { href: "/evaluation",    label: "Evaluation",    icon: BarChart3 },
  { href: "/observability", label: "Observability", icon: Activity },
  { href: "/integrations",  label: "MCP Integrations", icon: Plug },
];

export function Sidebar() {
  const path = usePathname();

  return (
    <aside className="w-56 flex-shrink-0 bg-surface border-r border-border flex flex-col h-screen sticky top-0 z-30">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-primary-gradient flex items-center justify-center shadow-glow-primary">
            <Cpu size={14} className="text-white" />
          </div>
          <div>
            <div className="font-display font-700 text-sm text-text tracking-tight leading-none">
              Recruit<span className="text-primary">AI</span>
            </div>
            <div className="text-[9px] text-text-faint font-mono mt-0.5 tracking-widest uppercase">
              Multi-Agent Platform
            </div>
          </div>
        </div>
      </div>

      {/* System status pill */}
      <div className="px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2 text-[10px] font-mono text-success">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-success" />
          </span>
          System Healthy
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 overflow-y-auto">
        <div className="section-eyebrow px-2 mb-2">Navigation</div>
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-all duration-150 mb-0.5",
                active
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "text-text-muted hover:text-text hover:bg-card"
              )}
            >
              <Icon size={14} className={active ? "text-primary" : "text-text-faint"} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="p-3 border-t border-border">
        <Link
          href="/settings"
          className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium text-text-muted hover:text-text hover:bg-card transition-colors"
        >
          <Settings size={14} />
          Settings
        </Link>
        <div className="mt-2 px-2.5">
          <div className="text-[9px] font-mono text-text-faint">v2.0.0-alpha</div>
        </div>
      </div>
    </aside>
  );
}