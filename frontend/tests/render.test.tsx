import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { Feedback, Pill, SafetyNotice, Table } from "@/components/ui";
import { api, ApiError, SAFETY_NOTICE } from "@/lib/api";

afterEach(cleanup);

describe("shared components", () => {
  it("shows the mandatory safety notice", () => {
    render(<SafetyNotice />);
    expect(screen.getByRole("note").textContent).toContain("educational demonstration");
    expect(SAFETY_NOTICE).toContain("A qualified pharmacist must verify");
  });

  it("renders loading, error and success states", () => {
    render(<Feedback loading error="boom" success="done" />);
    expect(screen.getByText("Loading…")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toBe("boom");
    expect(screen.getByRole("status").textContent).toBe("done");
  });

  it("renders table rows from data and an empty state", () => {
    const { rerender } = render(<Table columns={[{ key: "name", label: "Name" }]} rows={[{ name: "Pyrelief" }]} />);
    expect(screen.getByText("Pyrelief")).toBeTruthy();
    rerender(<Table columns={[{ key: "name", label: "Name" }]} rows={[]} empty="No rows" />);
    expect(screen.getByText("No rows")).toBeTruthy();
  });

  it("renders availability pills", () => {
    render(<Pill value="In stock" />);
    expect(screen.getByText("In stock").className).toContain("pill-in-stock");
  });
});

describe("api client", () => {
  it("turns an error response into ApiError with the backend detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 403, statusText: "Forbidden", json: async () => ({ detail: "Your role is not allowed to do this" }) }));
    await expect(api("/inventory")).rejects.toMatchObject({ status: 403, message: "Your role is not allowed to do this" });
    await waitFor(() => expect(new ApiError(1, "x").status).toBe(1));
    vi.unstubAllGlobals();
  });

  it("calls the same-origin /api prefix with credentials", async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", f);
    await api("/auth/me");
    expect(f.mock.calls[0][0]).toBe("/api/auth/me");
    expect(f.mock.calls[0][1].credentials).toBe("same-origin");
    vi.unstubAllGlobals();
  });
});
