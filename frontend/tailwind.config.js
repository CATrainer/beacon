/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dense, functional internal-tool palette.
        ink: "#0f172a",
        panel: "#ffffff",
        canvas: "#f1f5f9",
        line: "#e2e8f0",
        accent: "#1d4ed8",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
