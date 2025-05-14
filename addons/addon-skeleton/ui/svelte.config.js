import adapter from "@sveltejs/adapter-static";
import { addonDir } from "./qi.addon.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter(),
    paths: {
      base: `/${addonDir}`,
      relative: true,
    },
  },
};

export default config;
