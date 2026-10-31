// Server-side data-layer connection (like the slide's db.ts, which creates the PostgreSQL pool).
//
// In this project the relational database (MySQL) is owned by the FastAPI backend: it holds one connection pool per
// MySQL role and sets the request identity. Next.js must NOT open MySQL itself (it would bypass the role-based access
// design), so this module creates the pool of keep-alive HTTP connections that route handlers use to reach it.
import { Agent, fetch as undiciFetch } from "undici";

export const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// connection pool: up to 10 reusable keep-alive connections to the backend
const pool = new Agent({ connections: 10, keepAliveTimeout: 10_000 });

export async function dbFetch(path: string, init: { method?: string; headers?: Record<string, string>; body?: string } = {}) {
  const res = await undiciFetch(`${BACKEND_URL}${path}`, { ...init, dispatcher: pool });
  const text = await res.text();
  let data: unknown = text;
  try {
    data = JSON.parse(text);
  } catch {
    /* keep text */
  }
  return { ok: res.ok, status: res.status, data };
}
