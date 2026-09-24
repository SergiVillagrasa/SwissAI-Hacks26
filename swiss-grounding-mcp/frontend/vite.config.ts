import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve:
    mode === "test"
      ? {
          alias: {
            // mapbox-gl's real bundle needs a browser WebGL environment
            // and fails to load under jsdom; see src/test/mapboxGlStub.ts.
            "mapbox-gl": path.resolve(import.meta.dirname, "src/test/mapboxGlStub.ts"),
          },
        }
      : undefined,
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
}));
