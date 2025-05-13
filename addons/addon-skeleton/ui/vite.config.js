import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import path from "path";
import { fileURLToPath } from "url";

function qiHeader(addon) {
  return {
    name: "qi-addon-header",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        res.setHeader("X-Qi-Addon", addon);
        next();
      });
      // also serve a ping route for faster probing
      server.middlewares.use("/healthcheck", (req, res, next) => {
        res.setHeader("X-Qi-Addon", addon);
        res.end("Ui server is running.");
      });
    },
  };
}

// Get the directory of this config file
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const parentDir = path.basename(path.dirname(__dirname));

export default defineConfig({
  plugins: [sveltekit(), qiHeader(parentDir)],
  server: { host: "127.0.0.1" },
});
