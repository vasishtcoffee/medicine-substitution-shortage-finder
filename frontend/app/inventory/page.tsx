"use client";
import { useState, type FormEvent } from "react";
import { RoleGate, useAuth } from "@/lib/auth";
import { api, fmtDate, useApi } from "@/lib/api";
import { Feedback, Pill, Table, confirmAction } from "@/components/ui";

type Inv = { pharmacy_id: number; pharmacy_name: string; medicine_id: number; medicine_name: string; quantity: number; reorder_level: number; availability: string };
type Alert = { id: number; pharmacy_name: string; medicine_name: string; status: string; quantity_at_open: number; opened_at: string; resolved_at: string | null };
type Mov = { id: number; medicine_name: string; movement_type: string; delta: number; batch_no: string | null; expiry_date: string | null; created_at: string };
type Med = { id: number; name: string };

export default function InventoryPage() {
  return (
    <RoleGate roles={["pharmacist", "admin"]}>
      <Inventory />
    </RoleGate>
  );
}

function Inventory() {
  const { user } = useAuth();
  const inv = useApi<Inv[]>("/inventory");
  const alerts = useApi<Alert[]>("/alerts?status=OPEN");
  const moves = useApi<Mov[]>("/inventory/movements?limit=15");
  const meds = useApi<Med[]>("/medicines");
  const pharmacies = useApi<{ id: number; name: string }[]>("/pharmacies");
  const [pharmacy, setPharmacy] = useState<number | "">(user?.pharmacy_id ?? "");
  const [medicine, setMedicine] = useState<number | "">("");
  const [qty, setQty] = useState(10);
  const [batch, setBatch] = useState("");
  const [expiry, setExpiry] = useState("");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  function refresh() {
    inv.reload();
    alerts.reload();
    moves.reload();
  }

  async function receive(e: FormEvent) {
    e.preventDefault();
    if (pharmacy === "" || medicine === "") return setMsg({ err: "Choose pharmacy and medicine" });
    if (!confirmAction(`Record receipt of ${qty} units?`)) return;
    try {
      const r = await api<{ quantity: number }>("/inventory/receive", { body: { pharmacy_id: pharmacy, medicine_id: medicine, quantity: qty, batch_no: batch || null, expiry_date: expiry || null } });
      setMsg({ ok: `Stock received. New quantity: ${r.quantity}` });
      refresh();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function setReorder(row: Inv) {
    const v = window.prompt(`New reorder level for ${row.medicine_name}`, String(row.reorder_level));
    if (v === null) return;
    try {
      await api("/inventory/reorder-level", { method: "PUT", body: { pharmacy_id: row.pharmacy_id, medicine_id: row.medicine_id, reorder_level: Number(v) } });
      setMsg({ ok: "Reorder level updated." });
      refresh();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  return (
    <>
      <h1>Inventory &amp; low-stock alerts</h1>
      <p className="muted">Exact quantities are visible to pharmacy staff only; patients see availability bands. Alerts are created by a database trigger.</p>
      <Feedback error={msg.err} success={msg.ok} />

      <form className="card" onSubmit={receive}>
        <h2>Receive stock</h2>
        <div className="row">
          <label>Pharmacy
            <select value={pharmacy} onChange={(e) => setPharmacy(e.target.value ? Number(e.target.value) : "")} disabled={user?.role === "pharmacist"}>
              <option value="">— choose —</option>
              {pharmacies.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>Medicine
            <select value={medicine} onChange={(e) => setMedicine(e.target.value ? Number(e.target.value) : "")}>
              <option value="">— choose —</option>
              {meds.data?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </label>
          <label>Quantity<input type="number" min={1} value={qty} onChange={(e) => setQty(Number(e.target.value))} /></label>
          <label>Batch no.<input value={batch} maxLength={40} onChange={(e) => setBatch(e.target.value)} /></label>
          <label>Expiry<input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} /></label>
          <button type="submit">Receive</button>
        </div>
      </form>

      <h2>Open low-stock alerts</h2>
      <Feedback loading={alerts.loading} error={alerts.error} />
      <Table
        columns={[
          { key: "pharmacy_name", label: "Pharmacy" }, { key: "medicine_name", label: "Medicine" },
          { key: "quantity_at_open", label: "Qty when opened" }, { key: "opened_at", label: "Opened", render: (r) => fmtDate(String(r.opened_at)) },
        ]}
        rows={(alerts.data ?? []) as unknown as Record<string, unknown>[]}
        empty="No open alerts."
      />

      <h2>Stock</h2>
      <Feedback loading={inv.loading} error={inv.error} />
      <Table
        columns={[
          { key: "pharmacy_name", label: "Pharmacy" }, { key: "medicine_name", label: "Medicine" },
          { key: "quantity", label: "Qty" }, { key: "reorder_level", label: "Reorder at" },
          { key: "availability", label: "Band", render: (r) => <Pill value={String(r.availability)} /> },
          { key: "act", label: "", render: (r) => <button className="secondary" onClick={() => setReorder(r as unknown as Inv)}>Set reorder level</button> },
        ]}
        rows={(inv.data ?? []) as unknown as Record<string, unknown>[]}
      />

      <h2>Recent movements (ledger)</h2>
      <Table
        columns={[
          { key: "created_at", label: "When", render: (r) => fmtDate(String(r.created_at)) }, { key: "medicine_name", label: "Medicine" },
          { key: "movement_type", label: "Type", render: (r) => <Pill value={String(r.movement_type)} /> },
          { key: "delta", label: "Δ" }, { key: "batch_no", label: "Batch" }, { key: "expiry_date", label: "Expiry" },
        ]}
        rows={(moves.data ?? []) as unknown as Record<string, unknown>[]}
        empty="No movements yet."
      />
    </>
  );
}
