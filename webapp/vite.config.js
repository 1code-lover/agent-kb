import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const host = env.KB_WEBAPP_HOST || "127.0.0.1";
  const port = Number(env.KB_WEBAPP_PORT || "5173");

  return {
    base: "./",
    plugins: [react()],
    server: {
      host,
      port
    }
  };
});
