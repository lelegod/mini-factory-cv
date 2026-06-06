import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { mono: ["Martian Mono", "monospace"] },
      colors: {
        approved: "#22C55E",
        defective: "#EF4444",
        bg: "#0C0C0C",
        surface: "#111111",
        border: "#1e1e1e",
        muted: "#555555",
        dim: "#333333",
      },
    },
  },
  plugins: [],
};
export default config;
