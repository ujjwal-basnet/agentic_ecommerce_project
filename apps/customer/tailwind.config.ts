import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        /* Apple-inspired neutral palette */
        primary: {
          DEFAULT: "#1d1d1f",   /* near-black for primary actions */
          dim: "#333336",
          light: "#6e6e73",
          container: "#f5f5f7",
          "on-container": "#1d1d1f",
        },
        "on-primary": {
          DEFAULT: "#ffffff",
        },
        surface: {
          DEFAULT: "#fafafa",
          dim: "#f2f2f7",
          bright: "#ffffff",
          "container-lowest": "#ffffff",
          "container-low": "#f5f5f7",
          container: "#efefef",
          "container-high": "#e8e8ed",
          "container-highest": "#d1d1d6",
          variant: "#e5e5ea",
          tint: "#1d1d1f",
        },
        "on-surface": {
          DEFAULT: "#1d1d1f",
          variant: "#86868b",
        },
        background: "#fafafa",
        "on-background": "#1d1d1f",
        outline: {
          DEFAULT: "#86868b",
          variant: "#d1d1d6",
        },
        error: {
          DEFAULT: "#ff3b30",
          dim: "#d70015",
          container: "#fff2f0",
        },
        "on-error": {
          DEFAULT: "#ffffff",
          container: "#d70015",
        },
        success: {
          DEFAULT: "#34c759",
          container: "#f0fff4",
          "on-container": "#0a6629",
        },
        warning: {
          DEFAULT: "#ff9500",
          container: "#fff8ee",
          "on-container": "#8a5100",
        },
      },
      fontFamily: {
        headline: ["var(--font-manrope)", "system-ui", "sans-serif"],
        body: ["var(--font-inter)", "system-ui", "sans-serif"],
        label: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.06)",
        floating: "0 8px 32px rgba(0,0,0,0.1)",
        subtle: "0 1px 2px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};
export default config;
