import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        panel: "rgba(8, 24, 56, 0.84)",
        cyanLine: "#19d8ff",
        signalGreen: "#39e58c",
        warningGold: "#f5c84b"
      }
    }
  },
  plugins: []
};

export default config;
