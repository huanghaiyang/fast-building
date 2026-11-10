import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5120,
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
