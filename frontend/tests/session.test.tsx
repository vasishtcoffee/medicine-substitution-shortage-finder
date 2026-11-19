import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { NextRequest } from "next/server";
import { proxy } from "../proxy";
import { api } from "@/lib/api";
import { AuthProvider, RoleGate } from "@/lib/auth";

const router = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

describe("session recovery", () => {
  it.each([undefined, "not.a.jwt"])("keeps login reachable with cookie %s", (cookie) => {
    const response = proxy(new NextRequest("http://localhost/login", { headers: cookie ? { cookie: `medsub_session=${cookie}` } : {} }));
    expect(response.headers.get("location")).toBeNull();
  });
  it("redirects an absent session to login", () => {
    expect(proxy(new NextRequest("http://localhost/dashboard")).headers.get("location")).toBe("http://localhost/login");
  });
  it("lets the backend validate cookies on protected pages", () => {
    expect(proxy(new NextRequest("http://localhost/dashboard", { headers: { cookie: "medsub_session=invalid" } })).headers.get("location")).toBeNull();
  });
  it.each([401, 403])("handles API %s without conflating denial and expiry", async (status) => {
    const recover = vi.fn();
    window.addEventListener("medsub:session-expired", recover);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status, json: async () => ({ detail: "Denied" }) }));
    try {
      await expect(api("/inventory")).rejects.toMatchObject({ status });
      expect(recover).toHaveBeenCalledTimes(status === 401 ? 1 : 0);
    } finally { window.removeEventListener("medsub:session-expired", recover); }
  });
  it("clears a loaded identity and redirects on session expiry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 4, role: "patient" }) }));
    render(<AuthProvider><RoleGate roles={["patient"]}><p>Patient workspace</p></RoleGate></AuthProvider>);
    await screen.findByText("Patient workspace");
    window.dispatchEvent(new Event("medsub:session-expired"));
    await waitFor(() => expect(screen.queryByText("Patient workspace")).toBeNull());
    expect(router.replace).toHaveBeenCalledWith("/login");
  });
  it("recovers when initial identity validation returns 401", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: "Invalid session" }) }));
    render(<AuthProvider><RoleGate roles={["patient"]}><p>Patient workspace</p></RoleGate></AuthProvider>);
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Patient workspace")).toBeNull();
  });
});
