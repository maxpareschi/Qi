import { fileURLToPath } from "url";
import path from "path";
import { resolve } from "path";

const this_filename = fileURLToPath(import.meta.url);
const this_dirname = path.dirname(this_filename);

export function qiHeader(addon) {
  return {
    name: "qi-addon-header",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        res.setHeader("X-Qi-Addon", addon);
        next();
      });
      // also serve a ping route for faster probing
      server.middlewares.use("/vite", (req, res, next) => {
        res.setHeader("X-Qi-Addon", addon);
        res.end("Ui server is running.");
      });
    },
  };
}

export const addonName = path.basename(path.dirname(this_dirname));
export const addonDir = resolve(this_dirname);
export const addonBuildDir = resolve(path.dirname(this_dirname), "ui-dist");
