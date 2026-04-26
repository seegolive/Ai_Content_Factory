import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0A0A0F",
        surface: "#13131A",
        border: "#1E1E2E",
        primary: {
          DEFAULT: "#6C63FF",
          foreground: "#FFFFFF",
        },
        secondary: {
          DEFAULT: "#00D4AA",
          foreground: "#0A0A0F",
        },
        accent: {
          DEFAULT: "#FF6B6B",
          foreground: "#FFFFFF",
        },
        muted: {
          DEFAULT: "#1E1E2E",
          foreground: "#6B6B8A",
        },
        foreground: "#E8E8F0",
        "foreground-muted": "#6B6B8A",
        destructive: {
          DEFAULT: "#FF4444",
          foreground: "#FFFFFF",
        },
        success: {
          DEFAULT: "#00D4AA",
          foreground: "#0A0A0F",
        },
        warning: {
          DEFAULT: "#F59E0B",
          foreground: "#0A0A0F",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      backdropBlur: {
        xs: "2px",
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-in-out",
        "slide-in": "slideIn 0.2s ease-out",
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideIn: {
          "0%": { transform: "translateX(-10px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
