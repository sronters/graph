import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "GRAPHTRUST_");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": environment.GRAPHTRUST_API_PROXY ?? "http://127.0.0.1:8000" },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      css: true,
    },
  };
});
