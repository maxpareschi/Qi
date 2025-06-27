import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import { qiHeader, extensionName } from "./qi.dev.extension.js";

export default defineConfig({
  plugins: [sveltekit(), qiHeader(extensionName)],
  server: { host: "localhost" },
});
