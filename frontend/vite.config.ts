/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// https://vite.dev/config/
export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd())
  const isBackendLocal = env.VITE_BACKEND_LOCAL === "true";
  return {
    plugins: [
      tailwindcss(),
      react({
        babel: {
          plugins: [["babel-plugin-react-compiler"]],
        },
      }),
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      proxy: {
        ...(isBackendLocal
          ? {
              "/api": {
                target: "http://localhost:8866",
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, ""),
              },
            }
          : {
              "/api": {
                target: "http://localhost:9080",
                changeOrigin: true,
              },
            }),
        "/oauth2": {
          target: "http://localhost:9080",
          changeOrigin: true,
        },
        "/apps": {
          target: "http://localhost:9080",
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.{test,spec}.{ts,tsx}"],
      css: true,
    },
  };
});
