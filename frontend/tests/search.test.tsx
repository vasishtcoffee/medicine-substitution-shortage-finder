import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import SearchPage from "@/app/search/page";

const mockApi = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { role: "patient", pharmacy_id: 1 } }),
  RoleGate: ({ children }: { children: ReactNode }) => children,
}));
vi.mock("@/lib/api", () => ({ api: mockApi, useApi: () => ({ data: [{ id: 1, name: "City Care" }, { id: 2, name: "Green Cross" }] }) }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const medicine = { id: 1, name: "Paracetamol 500 mg Tablet", brand: "Generic", category: "Analgesics", dosage_form: "tablet", composition: "Paracetamol 500 mg", availability: [] };
const candidates = { requested: medicine, candidates: [], rejected: [], status: "PENDING_PHARMACIST_VERIFICATION" };

function search(text = "Paracetamol") {
  fireEvent.change(screen.getByRole("textbox", { name: "Medicine, brand, ingredient or category" }), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
}

describe("search task freshness", () => {
  it("clears the previous order form when a new search starts", async () => {
    mockApi.mockResolvedValueOnce({ results: [medicine] }).mockResolvedValueOnce({ results: [] });
    render(<SearchPage />);
    search();
    const result = await screen.findByRole("article", { name: medicine.name });
    fireEvent.click(within(result).getByRole("button", { name: "Order…" }));
    expect(screen.getByRole("heading", { name: `Request ${medicine.name}` })).toBeTruthy();
    search("no-such-medicine");
    await screen.findByText("No medicines match.");
    expect(screen.queryByRole("heading", { name: `Request ${medicine.name}` })).toBeNull();
  });

  it("invalidates a pending candidate response when the pharmacy changes", async () => {
    let resolve!: (value: unknown) => void;
    mockApi.mockResolvedValueOnce({ results: [medicine] }).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    render(<SearchPage />);
    search();
    fireEvent.click(within(await screen.findByRole("article", { name: medicine.name })).getByRole("button", { name: "Find verified-composition candidates" }));
    fireEvent.change(screen.getByRole("combobox", { name: "My pharmacy (for ranking)" }), { target: { value: "2" } });
    await act(async () => resolve(candidates));
    expect(screen.queryByRole("heading", { name: `Candidates for ${medicine.name}` })).toBeNull();
    expect(screen.queryByText("Loading…")).toBeNull();
  });

  it("keeps the latest search after responses arrive out of order", async () => {
    let resolveOld!: (value: unknown) => void;
    mockApi.mockReturnValueOnce(new Promise((done) => { resolveOld = done; })).mockResolvedValueOnce({ results: [] });
    render(<SearchPage />);
    search();
    search("no-such-medicine");
    await screen.findByText("No medicines match.");
    await act(async () => resolveOld({ results: [medicine] }));
    await waitFor(() => expect(screen.queryByRole("article", { name: medicine.name })).toBeNull());
    expect(screen.getByText("No medicines match.")).toBeTruthy();
  });
});
