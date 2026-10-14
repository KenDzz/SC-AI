/** @type {import('tailwindcss').Config} */
// Trung Nguyên Legend brand tokens, taken from the "Safety Monitor" design. Usage rules: docs/BRAND.md
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Espresso surfaces: sidebar, dark cards, primary buttons.
        ink: {
          DEFAULT: "#17110C",
          soft: "#2C2016",
          raised: "#221810",
          edge: "#33261B",
          field: "#3A2C20",
        },
        paper: "#F3EDE3",
        surface: "#FFFDF9",
        cream: "#FBF7F0",
        sand: "#F8F2E8",
        well: "#EAE1D2",
        line: {
          DEFAULT: "#E6DCCB",
          soft: "#F0E8DB",
          muted: "#EEE4D4",
          strong: "#DCCFB9",
        },
        // Text on light surfaces.
        bark: {
          300: "#A3927F",
          400: "#8A7866",
          500: "#7A6A5A",
          600: "#5E4E3F",
          800: "#2A1E15",
          900: "#1E150E",
        },
        // Text on espresso surfaces.
        husk: {
          50: "#FBF4E8",
          100: "#EFE4D2",
          300: "#BCA98F",
          500: "#8C7A64",
          700: "#6E5D4A",
        },
        gold: {
          50: "#FBF4E6",
          100: "#F7ECD6",
          200: "#F3DEB0",
          300: "#E3BE74",
          400: "#D9B56A",
          500: "#C99A4A",
          600: "#B4873A",
          700: "#8A5A0E",
          800: "#5E3D08",
        },
        crimson: {
          50: "#FFF8F4",
          100: "#F4DDD8",
          300: "#E8A497",
          500: "#D2402F",
          600: "#9E2A1F",
          700: "#8E2219",
          800: "#86221A",
        },
        leaf: {
          50: "#E6F0E5",
          200: "#C6DCC5",
          600: "#3E8A52",
          700: "#2F6E40",
          900: "#24502F",
        },
        toggle: "#D6CABA",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"],
        display: ["var(--font-display)", "Trajan Pro", "Times New Roman", "serif"],
        mono: ["var(--font-mono)", "Consolas", "monospace"],
      },
      backgroundImage: {
        rays: "repeating-conic-gradient(rgba(201,154,74,.2) 0 4deg, transparent 4deg 18deg)",
        "rays-soft": "repeating-conic-gradient(rgba(201,154,74,.14) 0 3deg, transparent 3deg 15deg)",
        stripes: "repeating-linear-gradient(135deg, #221810 0 10px, #2B1F15 10px 20px)",
        "gold-bar": "linear-gradient(180deg, #D9B56A, #B4873A)",
      },
      keyframes: {
        "live-pulse": {
          "0%": { boxShadow: "0 0 0 0 rgba(62,138,82,.55)" },
          "70%": { boxShadow: "0 0 0 8px rgba(62,138,82,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(62,138,82,0)" },
        },
        "demo-pulse": {
          "0%": { boxShadow: "0 0 0 0 rgba(217,119,6,.55)" },
          "70%": { boxShadow: "0 0 0 8px rgba(217,119,6,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(217,119,6,0)" },
        },
        rec: { "0%, 100%": { opacity: "1" }, "50%": { opacity: ".25" } },
        scan: { "0%": { top: "-3%" }, "100%": { top: "103%" } },
        "slide-in": { from: { opacity: "0", transform: "translateX(24px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: {
        "live-pulse": "live-pulse 2s infinite",
        "demo-pulse": "demo-pulse 2s infinite",
        rec: "rec 1.4s ease-in-out infinite",
        scan: "scan 4.5s linear infinite",
        "slide-in": "slide-in .28s cubic-bezier(.2,.8,.2,1)",
      },
    },
  },
  plugins: [],
};
