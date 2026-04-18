import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Legacy tokens kept for inventory page compatibility
        brand: { 50: "#f0f9ff", 100: "#e0f2fe", 500: "#0ea5e9", 600: "#0284c7", 700: "#0369a1" },
        panel: "#ffffff",
        soft: { DEFAULT: "#f1f4f6", 2: "#eaeff1" },
        muted: { DEFAULT: "#586064", 2: "#7b8488" },
        line: "rgba(171,179,183,0.15)",
        "purple-soft": "#d8d1ee",
        "purple-text": "#4f4b67",
        "red-soft": "#f2c0bb",
        "red-text": "#752121",
        "blue-soft": "#dce2f3",
        "blue-text": "#4b525f",

        // Lumière Noir editorial tokens (shared with code.html)
        background: "#f8f9fa",
        "on-background": "#2b3437",
        surface: "#f8f9fa",
        "surface-bright": "#f8f9fa",
        "surface-dim": "#d1dce0",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f1f4f6",
        "surface-container": "#eaeff1",
        "surface-container-high": "#e2e9ec",
        "surface-container-highest": "#dbe4e7",
        "surface-variant": "#dbe4e7",
        primary: "#575e70",
        "primary-dim": "#4b5264",
        "primary-container": "#dce2f7",
        "on-primary": "#f7f7ff",
        "on-primary-container": "#4b5263",
        "secondary-container": "#dce2f3",
        "on-secondary-container": "#4b525f",
        "tertiary-container": "#d3ceef",
        "on-tertiary-container": "#47445f",
        "on-surface": "#2b3437",
        "on-surface-variant": "#586064",
        outline: "#737c7f",
        "outline-variant": "#abb3b7",
        "error-container": "#fe8983",
        "on-error-container": "#752121",
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
