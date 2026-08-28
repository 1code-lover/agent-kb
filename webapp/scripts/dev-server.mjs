import { createServer } from "vite";
import { fileURLToPath } from "node:url";

function parseCliOption(args, name, fallback) {
  const index = args.indexOf(name);
  if (index < 0 || index + 1 >= args.length) {
    return fallback;
  }
  return args[index + 1];
}

function resolveNodeModuleEntry(relativePath) {
  return fileURLToPath(new URL(`../node_modules/${relativePath}`, import.meta.url));
}

const webappRoot = fileURLToPath(new URL("../", import.meta.url));
const host = parseCliOption(process.argv.slice(2), "--host", process.env.KB_WEBAPP_HOST || "127.0.0.1");
const port = Number(parseCliOption(process.argv.slice(2), "--port", process.env.KB_WEBAPP_PORT || "5173"));
const alias = [
  { find: "react/jsx-dev-runtime", replacement: resolveNodeModuleEntry("react/jsx-dev-runtime.js") },
  { find: "react/jsx-runtime", replacement: resolveNodeModuleEntry("react/jsx-runtime.js") },
  { find: "react-dom/client", replacement: resolveNodeModuleEntry("react-dom/client.js") },
  {
    find: "use-sync-external-store/shim/with-selector.js",
    replacement: resolveNodeModuleEntry("use-sync-external-store/shim/with-selector.js"),
  },
  {
    find: "use-sync-external-store/shim/with-selector",
    replacement: resolveNodeModuleEntry("use-sync-external-store/shim/with-selector.js"),
  },
  { find: "zustand/vanilla", replacement: resolveNodeModuleEntry("zustand/esm/vanilla.mjs") },
  { find: "@tanstack/query-core", replacement: resolveNodeModuleEntry("@tanstack/query-core/build/modern/index.js") },
  { find: "@tanstack/react-query", replacement: resolveNodeModuleEntry("@tanstack/react-query/build/modern/index.js") },
  { find: "react-dom", replacement: resolveNodeModuleEntry("react-dom/index.js") },
  { find: "react", replacement: resolveNodeModuleEntry("react/index.js") },
  { find: "axios", replacement: resolveNodeModuleEntry("axios/index.js") },
  { find: "zustand", replacement: resolveNodeModuleEntry("zustand/esm/index.mjs") },
];

const server = await createServer({
  configFile: false,
  root: webappRoot,
  base: "./",
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  resolve: {
    alias,
  },
  optimizeDeps: {
    noDiscovery: true,
    include: [],
  },
  server: {
    host,
    port,
    strictPort: true,
  },
});

await server.listen();
server.printUrls();

const closeServer = async () => {
  await server.close();
  process.exit(0);
};

process.on("SIGINT", closeServer);
process.on("SIGTERM", closeServer);
