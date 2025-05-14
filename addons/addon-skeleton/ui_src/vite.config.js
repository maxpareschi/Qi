import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import { qiHeader, addonDir } from "./qi.addon.js";

export default defineConfig({
  base: `/${addonDir}/`,
  plugins: [sveltekit(), qiHeader(addonDir)],
  server: { host: "127.0.0.1" },
});
