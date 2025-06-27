import { fileURLToPath } from "url";
import path from "path";
import { resolve } from "path";

const this_filename = fileURLToPath(import.meta.url);
const this_dirname = path.dirname(this_filename);

export function qiHeader(extension) {
  return {
    name: "qi-extension-header",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        res.setHeader("X-Qi-Extension", extension);
        next();
      });
      // also serve a ping route for faster probing
      server.middlewares.use("/vite", (req, res, next) => {
        res.setHeader("X-Qi-Extension", extension);
        res.end("Ui server is running.");
      });
    },
  };
}

export const extensionName = path.basename(path.dirname(this_dirname));
export const extensionDir = resolve(this_dirname);
export const extensionBuildDir = resolve(path.dirname(this_dirname), "ui-dist");
