import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import qiHeader from "./vite.plugin.qi";
import path from "path";
import { fileURLToPath } from "url";

// Get the directory of this config file
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const parentDir = path.basename(path.dirname(__dirname));

export default defineConfig({
  plugins: [sveltekit(), qiHeader(parentDir)],
  server: { host: "127.0.0.1" },
});
