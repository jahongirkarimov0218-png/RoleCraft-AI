import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// The browser only talks to this origin; /api/* is proxied to the FastAPI backend.
// The destination is read when `next build` runs (rewrites are baked into the build).
const api = process.env.PROMPTGRAPHIFY_API_URL ?? "http://127.0.0.1:8000";

/** @type {import("next").NextConfig} */
const config = {
  reactStrictMode: true,
  poweredByHeader: false,
  // `next dev` would otherwise write assistant instruction files (AGENTS.md) into the repository.
  agentRules: false,
  // The repository root may have its own lockfile (another project); pin the workspace root to this folder.
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default config;
