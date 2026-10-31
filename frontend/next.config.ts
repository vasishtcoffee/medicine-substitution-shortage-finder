import type { NextConfig } from "next";

// The browser only talks to this Next origin. /api/* is proxied to FastAPI (no CORS, httpOnly cookie stays same-origin).
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
};

export default config;
