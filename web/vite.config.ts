import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" + hash routing: the built site works from any static host or sub-path (GitHub Pages, Cloudflare Pages)
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { chunkSizeWarningLimit: 2000 },
  optimizeDeps: { exclude: ["onnxruntime-web"] },
});
