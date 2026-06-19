import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:      "#0B1020",
        surface: "#111827",
        card:    "#1F2937",
        border:  "#374151",
        primary: { DEFAULT: "#6366F1", dim: "#4F46E5", glow: "rgba(99,102,241,0.15)" },
        success: { DEFAULT: "#10B981", dim: "#059669", glow: "rgba(16,185,129,0.12)" },
        warning: { DEFAULT: "#F59E0B", dim: "#D97706" },
        error:   { DEFAULT: "#EF4444", dim: "#DC2626" },
        text:    { DEFAULT: "#F9FAFB", muted: "#9CA3AF", faint: "#4B5563" },
      },
      fontFamily: {
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        body:    ["Inter", "system-ui", "sans-serif"],
        mono:    ["JetBrains Mono", "Fira Code", "monospace"],
      },
      backgroundImage: {
        "grid-pattern": "linear-gradient(rgba(99,102,241,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.03) 1px, transparent 1px)",
        "primary-gradient": "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
        "success-gradient": "linear-gradient(135deg, #10B981 0%, #059669 100%)",
      },
      backgroundSize: {
        "grid": "32px 32px",
      },
      boxShadow: {
        "glow-primary": "0 0 20px rgba(99,102,241,0.2)",
        "glow-success": "0 0 20px rgba(16,185,129,0.15)",
        "card": "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "flow": "flow 2s ease-in-out infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
      },
      keyframes: {
        flow: {
          "0%, 100%": { opacity: "0.3", transform: "scaleX(0.8)" },
          "50%": { opacity: "1", transform: "scaleX(1)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;