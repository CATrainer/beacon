import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In Docker the dev server must listen on 0.0.0.0 and poll for file changes
// (host-mounted volumes don't always emit fs events on Windows/WSL).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true },
  },
});
