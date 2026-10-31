"use client";
import { useState, type FormEvent } from "react";
import { RoleGate } from "@/lib/auth";
import { api, fmtDate, useApi } from "@/lib/api";
import { Feedback, Pill, Table, confirmAction } from "@/components/ui";

type FeedDoc = { _id: string; pharmacy_id: number; medicine_id: number; quantity: number; availability: string; source: string; last_updated: string; notes: string; flags: string[]; metadata: Record<string, unknown> };
type EventDoc = { _id: string; source: string; pharmacy_id?: number; medicine_id?: number; occurred_at: string; payload: Record<string, unknown>; notes: string; flags: string[] };
type Page<T> = { total: number; page: number; page_size: number; items: T[] };
type Outbox = { counts: Record<string, number>; rows: { id: number; operation: string; entity_id: string; status: string; attempts: number; last_error: string | null }[] };

export default function FeedLabPage() {
  return (
    <RoleGate roles={["admin"]}>
      <FeedLab />
    </RoleGate>
  );
}

function FeedLab() {
  const [pharmacy, setPharmacy] = useState("");
  const [medicine, setMedicine] = useState("");
  const [source, setSource] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [epage, setEpage] = useState(1);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  const fq = new URLSearchParams({ page: String(page), page_size: "8" });
  if (pharmacy) fq.set("pharmacy_id", pharmacy);
  if (medicine) fq.set("medicine_id", medicine);
  const eq = new URLSearchParams({ page: String(epage), page_size: "8" });
  if (pharmacy) eq.set("pharmacy_id", pharmacy);
  if (medicine) eq.set("medicine_id", medicine);
  if (source) eq.set("source", source);
  if (from) eq.set("date_from", from);
  if (to) eq.set("date_to", to);

  const feed = useApi<Page<FeedDoc>>(`/feed/inventory?${fq}`);
  const events = useApi<Page<EventDoc>>(`/feed/events?${eq}`);
  const outbox = useApi<Outbox>("/sync/outbox?limit=10");

  function refreshAll() {
    feed.reload();
    events.reload();
    outbox.reload();
  }

  async function call(label: string, path: string, method = "POST", body: unknown = {}, confirm?: string) {
    if (confirm && !confirmAction(confirm)) return;
    setMsg({});
    try {
      const r = await api<Record<string, unknown>>(path, { method, body });
      setMsg({ ok: `${label}: ${JSON.stringify(r).slice(0, 200)}` });
      refreshAll();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function editFeed(d: FeedDoc) {
    const notes = window.prompt(`Notes for ${d._id} (quantity cannot be edited — MySQL owns it)`, d.notes ?? "");
    if (notes === null) return;
    const meta = window.prompt("Metadata as JSON (free-form)", JSON.stringify(d.metadata ?? {}));
    if (meta === null) return;
    try {
      await call("Updated", `/feed/inventory/${encodeURIComponent(d._id)}`, "PATCH", { notes, metadata: JSON.parse(meta) });
    } catch {
      setMsg({ err: "Metadata must be valid JSON" });
    }
  }

  const [ev, setEv] = useState({ source: "import", pharmacy_id: "", medicine_id: "", payload: '{"supplier":"Demo Supplies","eta_days":3}', notes: "" });
  async function createEvent(e: FormEvent) {
    e.preventDefault();
    let payload: unknown;
    try {
      payload = JSON.parse(ev.payload);
    } catch {
      return setMsg({ err: "Payload must be valid JSON" });
    }
    await call("Event created", "/feed/events", "POST", {
      source: ev.source, payload, notes: ev.notes,
      pharmacy_id: ev.pharmacy_id ? Number(ev.pharmacy_id) : null, medicine_id: ev.medicine_id ? Number(ev.medicine_id) : null,
    });
  }

  return (
    <>
      <h1>Feed Lab (MongoDB)</h1>
      <p className="muted">MongoDB holds a non-authoritative inventory feed and a semi-structured event log. MySQL is the source of truth: deleting a document here never changes stock, and <em>Resync</em> rebuilds it.</p>
      <Feedback error={msg.err} success={msg.ok} />

      <div className="card">
        <h2>Outbox &amp; sync</h2>
        <p>
          {Object.entries(outbox.data?.counts ?? {}).map(([s, n]) => <span key={s} style={{ marginRight: 12 }}><Pill value={s} /> {n}</span>)}
        </p>
        <div className="row">
          <button onClick={() => call("Sync", "/sync/run")}>Run sync now</button>
          <button className="secondary" onClick={() => call("Resync", "/sync/resync", "POST", {}, "Re-enqueue every MySQL inventory row and rebuild the Mongo feed?")}>Resync all from MySQL</button>
          <button className="secondary" onClick={() => call("Retry", "/sync/retry-failed")}>Retry failed rows</button>
        </div>
        <Feedback loading={outbox.loading} error={outbox.error} />
        <Table
          columns={[{ key: "id", label: "#" }, { key: "operation", label: "Operation" }, { key: "entity_id", label: "Entity" }, { key: "status", label: "Status", render: (r) => <Pill value={String(r.status)} /> }, { key: "attempts", label: "Attempts" }, { key: "last_error", label: "Last error" }]}
          rows={(outbox.data?.rows ?? []) as unknown as Record<string, unknown>[]}
          empty="Outbox is empty."
        />
      </div>

      <div className="card">
        <h2>Filters</h2>
        <div className="row">
          <label>Pharmacy id<input value={pharmacy} onChange={(e) => { setPharmacy(e.target.value); setPage(1); setEpage(1); }} /></label>
          <label>Medicine id<input value={medicine} onChange={(e) => { setMedicine(e.target.value); setPage(1); setEpage(1); }} /></label>
          <label>Event source
            <select value={source} onChange={(e) => { setSource(e.target.value); setEpage(1); }}>
              <option value="">any</option><option>sale</option><option>receipt</option><option>adjustment</option><option>import</option>
            </select>
          </label>
          <label>From<input type="date" value={from} onChange={(e) => { setFrom(e.target.value); setEpage(1); }} /></label>
          <label>To<input type="date" value={to} onChange={(e) => { setTo(e.target.value); setEpage(1); }} /></label>
        </div>
      </div>

      <h2>inventory_feed documents ({feed.data?.total ?? 0})</h2>
      <Feedback loading={feed.loading} error={feed.error} />
      <Table
        columns={[
          { key: "_id", label: "_id" }, { key: "quantity", label: "Qty" }, { key: "availability", label: "Band", render: (r) => <Pill value={String(r.availability)} /> },
          { key: "source", label: "Source" }, { key: "last_updated", label: "Updated", render: (r) => fmtDate(String(r.last_updated)) },
          { key: "notes", label: "Notes" }, { key: "flags", label: "Flags", render: (r) => (r.flags as string[]).join(", ") },
          { key: "act", label: "", render: (r) => (
            <>
              <button className="secondary" onClick={() => editFeed(r as unknown as FeedDoc)}>Edit</button>{" "}
              <button className="danger" onClick={() => call("Deleted", `/feed/inventory/${encodeURIComponent(String(r._id))}`, "DELETE", undefined, `Delete Mongo document ${r._id}? MySQL stock is not affected.`)}>Delete</button>
            </>) },
        ]}
        rows={(feed.data?.items ?? []) as unknown as Record<string, unknown>[]}
      />
      <Pager page={page} setPage={setPage} total={feed.data?.total ?? 0} size={8} />

      <h2>feed_events ({events.data?.total ?? 0})</h2>
      <Feedback loading={events.loading} error={events.error} />
      <Table
        columns={[
          { key: "_id", label: "_id" }, { key: "source", label: "Source", render: (r) => <Pill value={String(r.source)} /> },
          { key: "occurred_at", label: "When", render: (r) => fmtDate(String(r.occurred_at)) },
          { key: "payload", label: "Payload", render: (r) => <code>{JSON.stringify(r.payload)}</code> }, { key: "notes", label: "Notes" },
          { key: "act", label: "", render: (r) => (
            <>
              <button className="secondary" onClick={() => { const n = window.prompt("Notes", String(r.notes ?? "")); if (n !== null) call("Updated", `/feed/events/${encodeURIComponent(String(r._id))}`, "PATCH", { notes: n }); }}>Annotate</button>{" "}
              <button className="danger" onClick={() => call("Deleted", `/feed/events/${encodeURIComponent(String(r._id))}`, "DELETE", undefined, `Delete event ${r._id}?`)}>Delete</button>
            </>) },
        ]}
        rows={(events.data?.items ?? []) as unknown as Record<string, unknown>[]}
      />
      <Pager page={epage} setPage={setEpage} total={events.data?.total ?? 0} size={8} />

      <form className="card" onSubmit={createEvent}>
        <h2>Create a manual event</h2>
        <div className="row">
          <label>Source<select value={ev.source} onChange={(e) => setEv({ ...ev, source: e.target.value })}><option>import</option><option>adjustment</option><option>receipt</option><option>sale</option></select></label>
          <label>Pharmacy id<input value={ev.pharmacy_id} onChange={(e) => setEv({ ...ev, pharmacy_id: e.target.value })} /></label>
          <label>Medicine id<input value={ev.medicine_id} onChange={(e) => setEv({ ...ev, medicine_id: e.target.value })} /></label>
          <label>Payload (JSON — any shape)<input value={ev.payload} onChange={(e) => setEv({ ...ev, payload: e.target.value })} /></label>
          <label>Notes<input value={ev.notes} onChange={(e) => setEv({ ...ev, notes: e.target.value })} /></label>
          <button type="submit">Create event</button>
        </div>
      </form>
    </>
  );
}

function Pager({ page, setPage, total, size }: { page: number; setPage: (n: number) => void; total: number; size: number }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="row">
      <button className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
      <span>Page {page} / {pages}</span>
      <button className="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
    </div>
  );
}
