import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // 固定 127.0.0.1:5120：避免 Vite 只绑定 ::1 或端口被占用时悄悄换端口，
    // 与 backend 的 CORS/代理配置保持一致（npm start 由 scripts/dev.mjs 统一启动）。
    host: "127.0.0.1",
    port: 5120,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8756",
      "/out": "http://127.0.0.1:8756",
      "/tex": "http://127.0.0.1:8756",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
