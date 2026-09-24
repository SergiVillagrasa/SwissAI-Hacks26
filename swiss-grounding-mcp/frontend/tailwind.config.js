/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "#0A84FF",
        "accent-dim": "#3d9bff",
        "accent-ink": "#0A5FC2",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Inter", "Segoe UI", "sans-serif"],
      },
      backgroundImage: {
        "sky-glow":
          "radial-gradient(120% 100% at 18% 0%, #eef6ff 0%, #cfe4ff 42%, #9dc6f8 76%, #7fb0ee 100%)",
        "pill-glow":
          "radial-gradient(60% 100% at 50% 30%, rgba(10,132,255,0.22) 0%, rgba(10,132,255,0) 70%)",
      },
      boxShadow: {
        glass:
          "0 1px 1px 0 rgba(255,255,255,0.7) inset, 0 20px 40px -20px rgba(35,90,170,0.35), 0 2px 8px -2px rgba(35,90,170,0.15)",
        "glass-sm":
          "0 1px 0 0 rgba(255,255,255,0.7) inset, 0 8px 20px -10px rgba(35,90,170,0.3)",
        "glass-pop":
          "0 1px 1px 0 rgba(255,255,255,0.8) inset, 0 28px 60px -24px rgba(20,70,150,0.45), 0 4px 12px -4px rgba(20,70,150,0.2)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(10px) scale(0.98)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
      },
      animation: {
        rise: "rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
    },
  },
  plugins: [],
};
