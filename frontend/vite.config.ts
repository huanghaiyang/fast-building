import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// 项目根目录（.env 所在位置）：frontend/vite.config.ts -> ..
const projectRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig(({ mode }) => {
  // 读取项目根目录 .env 的配置，前后端端口/地址只在这一个地方维护
  const env = loadEnv(mode, projectRoot, "");
  const backendHost = env.FB_HOST || "127.0.0.1";
  const backendPort = Number(env.FB_PORT || 8756);
  const frontendHost = env.FB_FRONTEND_HOST || "127.0.0.1";
  const frontendPort = Number(env.FB_FRONTEND_PORT || 5120);
  const target = `http://${backendHost}:${backendPort}`;

  return {
    plugins: [react()],
    // 让 Vite 从项目根目录读 .env（与后端、scripts/dev.mjs 共用同一份配置）
    envDir: projectRoot,
    server: {
      host: frontendHost,
      port: frontendPort,
      // 端口被占用时明确失败，避免悄悄换端口后与代理/文档不一致
      strictPort: true,
      proxy: {
        "/api": target,
        "/out": target,
        "/tex": target,
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
  };
});
