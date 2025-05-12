export default function qiHeader(addon) {
  return {
    name: "qi-addon-header",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        res.setHeader("X-Qi-Addon", addon);
        next();
      });
      // also serve a ping route for faster probing
      server.middlewares.use("/__qi_ping", (req, res, next) => {
        res.setHeader("X-Qi-Addon", addon);
        res.end("pong");
      });
    },
  };
}
