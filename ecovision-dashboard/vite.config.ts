import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" so the built site works from a subdirectory — GitHub Pages
// serves project sites from /<repo>/, and an absolute base would 404 every
// asset there.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", assetsInlineLimit: 4096 },
});
