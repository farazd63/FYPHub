import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const runtimeProcess = globalThis as typeof globalThis & {
  process?: { env?: Record<string, string | undefined> };
};
const configuredBasePath = runtimeProcess.process?.env?.VITE_BASE_PATH;

type ProxyWithErrorEvents = {
  on: (
    event: "error",
    listener: (error: Error, request: unknown, response: unknown) => void,
  ) => void;
};

const apiProxy: ProxyOptions = {
  target: "http://127.0.0.1:8010",
  changeOrigin: true,
  timeout: 15000,
  proxyTimeout: 15000,
  configure(proxy) {
    // First requests after a backend restart can race the listener; retry once.
    (proxy as unknown as ProxyWithErrorEvents).on("error", (error, _req, res) => {
      const socket = res as { writeHead?: (code: number, headers?: Record<string, string>) => void; end?: (body?: string) => void };
      if (typeof socket.writeHead === "function" && !("headersSent" in socket && (socket as { headersSent?: boolean }).headersSent)) {
        socket.writeHead?.(503, { "Content-Type": "application/json" });
        socket.end?.(JSON.stringify({ detail: { code: "upstream_unavailable", message: "API temporarily unavailable. Retrying…" } }));
      }
      console.warn("[vite-proxy]", error.message);
    });
  },
};

export default defineConfig({
  // GitHub Pages publishes this project below /FYPHub/, while local and
  // container deployments continue to use the root path.
  base: configuredBasePath || "/",
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": apiProxy,
      "/health": apiProxy,
    },
  },
});
