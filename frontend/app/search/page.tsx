"use client";
import { useState, type FormEvent } from "react";
import { RoleGate, useAuth } from "@/lib/auth";
import { api, useApi } from "@/lib/api";
import { Feedback, Pill, SafetyNotice, Table, confirmAction } from "@/components/ui";

type Band = { pharmacy_id: number; pharmacy_name: string; availability: string };
type Med = {
  id: number; name: string; brand: string; category: string; composition: string; dosage_form: string;
  requires_prescription: number; substitution_allowed: number; in_shortage: number; availability: Band[];
};
type Cand = {
  rank_position: number; medicine_id: number; name: string; brand: string; availability_here: string; quantity_here: number | null;
  pharmacies_stocking: number; total_quantity: number | null; open_low_stock_alerts: number; eligibility_reason: string; verification_status: string;
};
type Cands = {
  requested: { id: number; name: string }; candidates: Cand[]; rejected: { medicine_id: number; name: string; reject_reason: string }[];
  status: string; message?: string; notice: string;
};
type Pharmacy = { id: number; name: string };

export default function SearchPage() {
  return (
    <RoleGate roles={["patient", "pharmacist", "admin"]}>
      <Search />
    </RoleGate>
  );
}

function Search() {
  const { user } = useAuth();
  const pharmacies = useApi<Pharmacy[]>("/pharmacies");
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Med[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pharmacyId, setPharmacyId] = useState<number | "">(user?.pharmacy_id ?? "");
  const [cands, setCands] = useState<Cands | null>(null);
  const [candLoading, setCandLoading] = useState(false);
  const [candError, setCandError] = useState<string | null>(null);
  const [orderFor, setOrderFor] = useState<{ id: number; name: string } | null>(null);

  async function run(e?: FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    setCands(null);
    try {
      const r = await api<{ results: Med[] }>(`/search?q=${encodeURIComponent(q)}`);
      setResults(r.results);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function findSubstitutes(m: { id: number }) {
    setCandLoading(true);
    setCandError(null);
    try {
      const ph = pharmacyId === "" ? "" : `?pharmacy_id=${pharmacyId}`;
      setCands(await api<Cands>(`/search/candidates/${m.id}${ph}`));
    } catch (err) {
      setCandError((err as Error).message);
    } finally {
      setCandLoading(false);
    }
  }

  return (
    <>
      <h1>Search &amp; availability</h1>
      <SafetyNotice />
      <form onSubmit={run} className="row">
        <label>
          Medicine, brand, ingredient or category
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. paracetamol" />
        </label>
        <label>
          My pharmacy (for ranking)
          <select value={pharmacyId} onChange={(e) => setPharmacyId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">— any —</option>
            {pharmacies.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <button type="submit">Search</button>
      </form>
      <Feedback loading={loading} error={error} />
      {results && results.length === 0 && <p className="muted">No medicines match.</p>}
      {results?.map((m) => (
        <div className="card" key={m.id}>
          <strong>{m.name}</strong> <span className="muted">· {m.brand} · {m.category} · {m.dosage_form}</span>
          <div className="muted">{m.composition}</div>
          <div>
            {m.requires_prescription ? <Pill value="Prescription" /> : null} {m.in_shortage ? <Pill value="Open shortage" /> : null}{" "}
            {!m.substitution_allowed ? <Pill value="No substitution" /> : null}
          </div>
          <p>
            {m.availability.map((a) => (
              <span key={a.pharmacy_id} style={{ marginRight: 12 }}>{a.pharmacy_name}: <Pill value={a.availability} /></span>
            ))}
          </p>
          <div className="row">
            <button className="secondary" onClick={() => findSubstitutes(m)}>Find verified-composition candidates</button>
            {user?.role === "patient" && <button onClick={() => setOrderFor({ id: m.id, name: m.name })}>Order…</button>}
          </div>
        </div>
      ))}
      <Feedback loading={candLoading} error={candError} />
      {cands && <Candidates data={cands} onOrder={user?.role === "patient" ? (id, name) => setOrderFor({ id, name }) : undefined} />}
      {orderFor && <OrderForm med={orderFor} pharmacies={pharmacies.data ?? []} defaultPharmacy={pharmacyId} onClose={() => setOrderFor(null)} />}
    </>
  );
}

function Candidates({ data, onOrder }: { data: Cands; onOrder?: (id: number, name: string) => void }) {
  return (
    <div className="card">
      <h2>Candidates for {data.requested.name}</h2>
      <p className="alert" style={{ background: "var(--warn-bg)", color: "var(--warn)" }}>
        Status: <strong>pending pharmacist verification</strong>. These are composition matches, not a recommendation to substitute.
      </p>
      {data.candidates.length === 0 ? (
        <p>{data.message ?? "No verified composition-matching candidate"}</p>
      ) : (
        <Table
          columns={[
            { key: "rank_position", label: "#" },
            { key: "name", label: "Medicine", render: (r) => `${r.name} (${r.brand})` },
            { key: "availability_here", label: "At chosen pharmacy", render: (r) => <Pill value={String(r.availability_here)} /> },
            { key: "pharmacies_stocking", label: "Pharmacies stocking" },
            { key: "quantity_here", label: "Units here (staff only)", render: (r) => (r.quantity_here ?? "hidden") as string },
            { key: "eligibility_reason", label: "Why eligible" },
            { key: "act", label: "", render: (r) => (onOrder ? <button className="secondary" onClick={() => onOrder(Number(r.medicine_id), String(r.name))}>Order…</button> : null) },
          ]}
          rows={data.candidates as unknown as Record<string, unknown>[]}
        />
      )}
      <h3>Rejected near-misses</h3>
      <Table
        columns={[{ key: "name", label: "Medicine" }, { key: "reject_reason", label: "Why it is NOT a match" }]}
        rows={data.rejected as unknown as Record<string, unknown>[]}
        empty="No near-misses."
      />
    </div>
  );
}

function OrderForm({ med, pharmacies, defaultPharmacy, onClose }: { med: { id: number; name: string }; pharmacies: Pharmacy[]; defaultPharmacy: number | ""; onClose: () => void }) {
  const [pharmacy, setPharmacy] = useState<number | "">(defaultPharmacy);
  const [qty, setQty] = useState(1);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pharmacy === "") return setMsg({ err: "Choose a pharmacy" });
    if (!confirmAction(`Request ${qty} × ${med.name}? A pharmacist will review it before any sale.`)) return;
    setBusy(true);
    try {
      const r = await api<{ order_id: number }>("/orders", { body: { pharmacy_id: pharmacy, medicine_id: med.id, quantity: qty, prescription_note: note || null } });
      setMsg({ ok: `Order #${r.order_id} requested. Track it under Orders.` });
    } catch (err) {
      setMsg({ err: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Request {med.name}</h2>
      <div className="row">
        <label>Pharmacy
          <select value={pharmacy} onChange={(e) => setPharmacy(e.target.value ? Number(e.target.value) : "")} required>
            <option value="">— choose —</option>
            {pharmacies.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label>Quantity
          <input type="number" min={1} max={1000} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
        </label>
        <label>Prescription note (short text)
          <input value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button type="submit" disabled={busy}>Request order</button>
        <button type="button" className="secondary" onClick={onClose}>Close</button>
      </div>
      <Feedback error={msg.err} success={msg.ok} />
    </form>
  );
}
