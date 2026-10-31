"use client";
import { useState } from "react";
import { RoleGate, useAuth } from "@/lib/auth";
import { api, fmtDate, useApi } from "@/lib/api";
import { Feedback, Pill, SafetyNotice, Table, confirmAction } from "@/components/ui";

type Item = { item_id: number; requested_medicine_id: number; requested_name: string; dispensed_medicine_id: number | null; dispensed_name: string | null; quantity: number; requires_prescription?: number };
type Order = { order_id: number; status: string; pharmacy_id: number; pharmacy_name: string; patient_name?: string; prescription_note: string | null; created_at: string; items: Item[] };
type Cand = { medicine_id: number; name: string; brand: string; availability_here: string; quantity_here: number | null; eligibility_reason: string };
type Cands = { candidates: Cand[]; rejected: { name: string; reject_reason: string }[]; message?: string };

export default function OrdersPage() {
  return (
    <RoleGate roles={["patient", "pharmacist"]}>
      <Orders />
    </RoleGate>
  );
}

function Orders() {
  const { user } = useAuth();
  const isPatient = user?.role === "patient";
  const { data, error, loading, reload } = useApi<Order[]>(isPatient ? "/orders/mine" : "/orders");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  async function act(label: string, path: string, body: unknown = {}, confirm?: string) {
    if (confirm && !confirmAction(confirm)) return;
    setMsg({});
    try {
      await api(path, { method: "POST", body });
      setMsg({ ok: `${label} done.` });
      reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  return (
    <>
      <h1>{isPatient ? "My orders" : `Orders — ${user?.pharmacy_id ? "my pharmacy" : ""}`}</h1>
      <SafetyNotice />
      <Feedback loading={loading} error={error} success={msg.ok} />
      {msg.err && <Feedback error={msg.err} />}
      {data && data.length === 0 && <p className="muted">No orders.</p>}
      {data?.map((o) => (
        <div className="card" key={o.order_id}>
          <h3>
            Order #{o.order_id} <Pill value={o.status} /> <span className="muted">{o.pharmacy_name} · {fmtDate(o.created_at)}{o.patient_name ? ` · ${o.patient_name}` : ""}</span>
          </h3>
          {o.prescription_note && <p className="muted">Prescription note: {o.prescription_note}</p>}
          {o.items.map((it) => (
            <div key={it.item_id} className="row">
              <span>
                {it.quantity} × {it.requested_name}
                {it.dispensed_name && it.dispensed_medicine_id !== it.requested_medicine_id && <> → dispensed as <strong>{it.dispensed_name}</strong></>}
              </span>
            </div>
          ))}
          {isPatient ? (
            <>
              <Reviews orderId={o.order_id} />
              {["REQUESTED", "UNDER_REVIEW", "APPROVED"].includes(o.status) && (
                <button className="danger" onClick={() => act("Cancel", `/orders/${o.order_id}/cancel`, {}, `Cancel order #${o.order_id}?`)}>Cancel order</button>
              )}
            </>
          ) : (
            <PharmacistActions order={o} act={act} />
          )}
        </div>
      ))}
    </>
  );
}

function Reviews({ orderId }: { orderId: number }) {
  const { data } = useApi<{ id: number; proposed_name: string; decision: string; note: string | null; eligibility_reason: string; reviewer_name: string }[]>(`/orders/${orderId}/reviews`);
  if (!data || data.length === 0) return null;
  return (
    <div>
      <h3>Pharmacist decisions</h3>
      {data.map((r) => <p key={r.id}><Pill value={r.decision} /> {r.proposed_name} — {r.eligibility_reason} <span className="muted">(by {r.reviewer_name}{r.note ? `: ${r.note}` : ""})</span></p>)}
    </div>
  );
}

function PharmacistActions({ order, act }: { order: Order; act: (l: string, p: string, b?: unknown, c?: string) => Promise<void> }) {
  const [cands, setCands] = useState<Record<number, Cands>>({});
  const [err, setErr] = useState<string | null>(null);
  const s = order.status;

  async function loadCands(it: Item) {
    setErr(null);
    try {
      setCands((c) => ({ ...c, [it.item_id]: undefined as unknown as Cands }));
      const d = await api<Cands>(`/search/candidates/${it.requested_medicine_id}?pharmacy_id=${order.pharmacy_id}`);
      setCands((c) => ({ ...c, [it.item_id]: d }));
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <div>
      <Feedback error={err} />
      {s === "REQUESTED" && <button onClick={() => act("Start review", `/orders/${order.order_id}/start-review`)}>Start review</button>}
      {s === "UNDER_REVIEW" && (
        <>
          {order.items.map((it) => (
            <div key={it.item_id} className="card">
              <strong>{it.requested_name}</strong>
              <div className="row">
                <button className="secondary" onClick={() => act("Dispense as requested", `/orders/items/${it.item_id}/decision`, { proposed_medicine_id: it.requested_medicine_id, decision: "APPROVED", note: "as requested" }, `Dispense ${it.requested_name} as requested?`)}>Dispense as requested</button>
                <button className="secondary" onClick={() => loadCands(it)}>Show composition-matching candidates</button>
              </div>
              {cands[it.item_id] && (
                <>
                  {cands[it.item_id].candidates.length === 0 && <p>{cands[it.item_id].message ?? "No verified composition-matching candidate"}</p>}
                  <Table
                    columns={[
                      { key: "name", label: "Candidate", render: (r) => `${r.name} (${r.brand})` },
                      { key: "availability_here", label: "Here", render: (r) => <Pill value={String(r.availability_here)} /> },
                      { key: "quantity_here", label: "Units here" },
                      { key: "eligibility_reason", label: "Why eligible" },
                      { key: "go", label: "", render: (r) => <button onClick={() => act("Substitution approval", `/orders/items/${it.item_id}/decision`, { proposed_medicine_id: r.medicine_id, decision: "APPROVED", note: "pharmacist verified" }, `I have verified that ${r.name} may replace ${it.requested_name}. Approve this substitution?`)}>Approve substitute</button> },
                    ]}
                    rows={cands[it.item_id].candidates as unknown as Record<string, unknown>[]}
                    empty="No eligible candidates."
                  />
                </>
              )}
            </div>
          ))}
          <div className="row">
            <button onClick={() => act("Approve order", `/orders/${order.order_id}/approve`, {}, `Approve order #${order.order_id}?`)}>Approve order</button>
            <button className="danger" onClick={() => act("Reject order", `/orders/${order.order_id}/reject`, {}, `Reject order #${order.order_id}?`)}>Reject order</button>
          </div>
        </>
      )}
      {s === "APPROVED" && (
        <div className="row">
          <button onClick={() => act("Sale", `/orders/${order.order_id}/complete`, {}, `Complete the sale for order #${order.order_id}? Stock will be deducted.`)}>Complete sale</button>
        </div>
      )}
      {["REQUESTED", "UNDER_REVIEW", "APPROVED"].includes(s) && (
        <button className="danger" onClick={() => act("Cancel", `/orders/${order.order_id}/cancel`, {}, `Cancel order #${order.order_id}?`)}>Cancel</button>
      )}
    </div>
  );
}
