// Server-side connection to the NoSQL side (the slide's redis.ts connects to Redis; this project uses MongoDB).
// MongoDB, like MySQL, is accessed only by the FastAPI backend (pymongo). This helper asks the backend whether the
// MongoDB feed is reachable, reusing the pooled connection from lib/db.ts.
import { dbFetch } from "./db";

export async function mongoStatus(cookie: string | null) {
  const r = await dbFetch("/sync/outbox?limit=1", { headers: cookie ? { cookie } : {} });
  // the endpoint is admin-only: 401/403 just means "not signed in as admin", not "MongoDB is down"
  if (r.status === 401 || r.status === 403) return { checked: false, reason: "admin sign-in required" };
  return { checked: true, outbox: (r.data as { counts?: Record<string, number> }).counts ?? {} };
}
