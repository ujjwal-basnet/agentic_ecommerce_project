import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#f0f9ff", 100: "#e0f2fe", 500: "#0ea5e9", 600: "#0284c7", 700: "#0369a1" },
        panel: "#ffffff",
        soft: { DEFAULT: "#f1f4f6", 2: "#eaeff1" },
        muted: { DEFAULT: "#586064", 2: "#7b8488" },
        line: "rgba(171,179,183,0.15)",
        "primary-dim": "#4b5264",
        "purple-soft": "#d8d1ee",
        "purple-text": "#4f4b67",
        "red-soft": "#f2c0bb",
        "red-text": "#752121",
        "blue-soft": "#dce2f3",
        "blue-text": "#4b525f",
      },
      fontFamily: {
        headline: ["var(--font-manrope)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
