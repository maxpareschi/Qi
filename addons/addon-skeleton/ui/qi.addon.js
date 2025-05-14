import { fileURLToPath } from "url";
import path from "path";

export function qiHeader(addon) {
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
export const addonDir = path.basename(path.dirname(__dirname));
