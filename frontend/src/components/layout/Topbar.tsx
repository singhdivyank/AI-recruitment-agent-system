"use client";
import { ReactNode } from "react";

interface TopbarProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  eyebrow?: string;
}

export function Topbar({ title, subtitle, actions, eyebrow }: TopbarProps) {
  return (
    <div className="border-b border-border bg-surface/80 backdrop-blur-sm sticky top-0 z-20 px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          {eyebrow && <div className="section-eyebrow mb-1">{eyebrow}</div>}
          <h1 className="font-display text-lg font-semibold text-text tracking-tight">{title}</h1>
          {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}