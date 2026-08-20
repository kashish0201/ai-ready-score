import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker Compose, set VITE_PROXY_TARGET=http://backend:8000 so the
// Vite server can reach the backend container. Locally, default to localhost.
const apiTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        timeout: 300000,
        proxyTimeout: 300000,
      },
    },
  },
});
