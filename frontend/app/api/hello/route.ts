// GET /api/hello : Next.js route handler (handles the API request, like the slide's route.ts).
// Proves the chain browser -> Next.js -> FastAPI -> MySQL is wired up. Everything else under /api/* is proxied to FastAPI.
import { NextResponse } from "next/server";
import { dbFetch } from "@/lib/db";
import { mongoStatus } from "@/lib/mongo";

export async function GET(req: Request) {
  try {
    const health = await dbFetch("/health");
    const mongo = await mongoStatus(req.headers.get("cookie"));
    return NextResponse.json({ message: "Hello from Next.js", backend: health.ok ? "up" : "down", mongo });
  } catch {
    return NextResponse.json({ message: "Hello from Next.js", backend: "unreachable" }, { status: 502 });
  }
}
