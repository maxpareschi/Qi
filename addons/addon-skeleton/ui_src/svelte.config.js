import adapter from "@sveltejs/adapter-static";
import { addonName, addonDir, addonBuildDir } from "./qi.addon.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter({
      pages: addonBuildDir,
      assets: addonBuildDir,
      fallback: "index.html",
      precompress: true,
      strict: true,
    }),
    paths: {
      base: `/${addonName}`,
      relative: false,
    },
  },
};

export default config;
