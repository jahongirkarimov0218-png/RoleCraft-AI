import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

// The browser only talks to this origin; /api/* is proxied to the FastAPI backend.
const api = process.env.PROMPTGRAPHIFY_API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // `next dev` would otherwise write assistant instruction files (AGENTS.md) into the repository.
  agentRules: false,
  // The repository root has its own lockfile (another project); pin the workspace root to this folder.
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default config;
