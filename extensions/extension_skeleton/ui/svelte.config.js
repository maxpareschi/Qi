import adapter from "@sveltejs/adapter-static";
import { extensionName, extensionBuildDir } from "./qi.dev.extension.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter({
      pages: extensionBuildDir,
      assets: extensionBuildDir,
      fallback: "index.html",
      precompress: true,
      strict: true,
    }),
    paths: {
      base: `/${extensionName}`,
      relative: false,
    },
  },
};

export default config;
