import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import { qiHeader, addonName } from "./qi.dev.addon.js";

export default defineConfig({
  plugins: [sveltekit(), qiHeader(addonName)],
  server: { host: "127.0.0.1" },
});
