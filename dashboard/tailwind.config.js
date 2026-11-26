/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0f14",
        panel: "#111823",
        line: "#1e2a3a",
        muted: "#7d8ea3",
        paper: "#e8eef6",
        healthy: "#3ddc97",
        drift: "#f5b544",
        down: "#ff5c7a",
        verified: "#5aa9ff",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
