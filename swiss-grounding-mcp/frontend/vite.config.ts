import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  if (env.VITE_MAPBOX_TOKEN?.startsWith("sk.")) {
    throw new Error(
      "VITE_MAPBOX_TOKEN must be a public pk. token; secret sk. tokens cannot be bundled."
    );
  }

  return {
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
  };
});
