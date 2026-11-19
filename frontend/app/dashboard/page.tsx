"use client";
import Link from "next/link";
import { useId } from "react";
import { RoleGate } from "@/lib/auth";
import { useApi } from "@/lib/api";
import { Feedback, statusPresentation } from "@/components/ui";

type Dash = {
  role: string; user: string; pharmacy?: string;
  my_orders_by_status?: Record<string, number>; orders_by_status?: Record<string, number>;
  open_low_stock_alerts?: number; open_shortages?: number; sync_pending?: number; users?: number;
};

function Stat({ label, value }: { label: string; value: number | string | undefined }) {
  const id = useId();
  return <article className="card" aria-labelledby={id}>
    <h2 id={id} className="stat-label">{label}</h2>
    <div className="stat">{value ?? 0}</div>
  </article>;
}

function Statuses({ title, counts }: { title: string; counts?: Record<string, number> }) {
  const id = useId();
  const entries = Object.entries(counts ?? {});
  return <section className="card" aria-labelledby={id}>
    <h2 id={id}>{title}</h2>
    {entries.length === 0 ? <p className="muted">No orders yet.</p> : <ul className="status-list">
      {entries.map(([s, n]) => { const status = statusPresentation(s); return <li key={s}>
        <span aria-hidden="true">{status.symbol}</span><span>{status.label}</span><span className="status-count">{n}</span>
      </li>; })}
    </ul>}
  </section>;
}

export default function DashboardPage() {
  return <RoleGate roles={["patient", "pharmacist", "admin"]}><Dashboard /></RoleGate>;
}

function Dashboard() {
  const { data, error, loading } = useApi<Dash>("/dashboard");
  return <>
    <h1>Dashboard{data?.pharmacy ? ` — ${data.pharmacy}` : ""}</h1>
    <Feedback loading={loading} error={error} />
    {data?.role === "patient" && <>
      <section className="card" aria-labelledby="find-medicine"><h2 id="find-medicine">Find a medicine</h2>
        <p className="muted">Search medicines, check pharmacy availability and request an order.</p>
        <Link className="button primary" href="/search">Search medicines</Link>
      </section>
      <div className="grid"><Stat label="Open medicine shortages" value={data.open_shortages} /></div>
      <Statuses title="My orders" counts={data.my_orders_by_status} />
      <section className="quick-links" aria-labelledby="patient-links"><h2 id="patient-links">Quick links</h2><ul><li><Link href="/orders">My orders</Link></li></ul></section>
    </>}
    {data?.role === "pharmacist" && <>
      <p><Link className="button primary" href="/orders">Review orders</Link></p>
      <div className="grid">
        <Stat label="Open low-stock alerts" value={data.open_low_stock_alerts} />
        <Stat label="Open shortages" value={data.open_shortages} />
      </div>
      <Statuses title="Orders at my pharmacy" counts={data.orders_by_status} />
      <section className="quick-links" aria-labelledby="pharmacy-links"><h2 id="pharmacy-links">Quick links</h2><ul><li><Link href="/inventory">Inventory &amp; alerts</Link></li></ul></section>
    </>}
    {data?.role === "admin" && <>
      <div className="grid">
        <Stat label="Open low-stock alerts" value={data.open_low_stock_alerts} />
        <Stat label="Open shortages" value={data.open_shortages} />
        <Stat label="Pending MongoDB sync" value={data.sync_pending} />
        <Stat label="Users" value={data.users} />
      </div>
      <Statuses title="All orders" counts={data.orders_by_status} />
      <section className="quick-links" aria-labelledby="admin-links"><h2 id="admin-links">Quick links</h2><ul>
        <li><Link href="/admin">Catalog, shortages &amp; users</Link></li>
      </ul></section>
    </>}
  </>;
}
