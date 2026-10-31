import { NextResponse, type NextRequest } from "next/server";

// UX redirect only: the FastAPI backend re-checks the signed cookie and the role on every request.
const COOKIE = "medsub_session";

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = req.cookies.has(COOKIE);
  if (pathname === "/login") {
    return hasSession ? NextResponse.redirect(new URL("/dashboard", req.url)) : NextResponse.next();
  }
  if (!hasSession) return NextResponse.redirect(new URL("/login", req.url));
  if (pathname === "/") return NextResponse.redirect(new URL("/dashboard", req.url));
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/login", "/dashboard/:path*", "/search/:path*", "/orders/:path*", "/inventory/:path*", "/admin/:path*", "/feed-lab/:path*"],
};
