import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#575e70", dim: "#4b5264", container: "#dce2f7", fixed: "#dce2f7", "fixed-dim": "#ced4e9" },
        "on-primary": { DEFAULT: "#f7f7ff", container: "#4b5263", fixed: "#383f50", "fixed-variant": "#545b6d" },
        secondary: { DEFAULT: "#585f6d", dim: "#4c5361", container: "#dce2f3", fixed: "#dce2f3", "fixed-dim": "#ced4e4" },
        "on-secondary": { DEFAULT: "#f8f8ff", container: "#4b525f", fixed: "#39404c", "fixed-variant": "#555c69" },
        tertiary: { DEFAULT: "#5f5c78", dim: "#53506b", container: "#d3ceef", fixed: "#d3ceef", "fixed-dim": "#c5c0e0" },
        "on-tertiary": { DEFAULT: "#fcf7ff", container: "#47445f", fixed: "#34314b", "fixed-variant": "#514d69" },
        surface: {
          DEFAULT: "#f8f9fa", dim: "#d1dce0", bright: "#f8f9fa",
          "container-lowest": "#ffffff", "container-low": "#f1f4f6",
          container: "#eaeff1", "container-high": "#e2e9ec", "container-highest": "#dbe4e7",
          variant: "#dbe4e7", tint: "#575e70",
        },
        "on-surface": { DEFAULT: "#2b3437", variant: "#586064" },
        background: "#f8f9fa",
        "on-background": "#2b3437",
        outline: { DEFAULT: "#737c7f", variant: "#abb3b7" },
        error: { DEFAULT: "#9f403d", dim: "#4e0309", container: "#fe8983" },
        "on-error": { DEFAULT: "#fff7f6", container: "#752121" },
        inverse: { surface: "#0c0f10", "on-surface": "#9b9d9e", primary: "#d9dff5" },
      },
      fontFamily: {
        headline: ["var(--font-manrope)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
        label: ["var(--font-inter)", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
