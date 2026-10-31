"use client";
import Link from "next/link";
import { RoleGate } from "@/lib/auth";
import { useApi } from "@/lib/api";
import { Feedback, Pill } from "@/components/ui";

type Dash = {
  role: string; user: string; pharmacy?: string;
  my_orders_by_status?: Record<string, number>; orders_by_status?: Record<string, number>;
  open_low_stock_alerts?: number; open_shortages?: number; sync_pending?: number; users?: number;
};

function Stat({ label, value }: { label: string; value: number | string | undefined }) {
  return (
    <div className="card">
      <div className="stat">{value ?? 0}</div>
      <div className="muted">{label}</div>
    </div>
  );
}

function Statuses({ title, counts }: { title: string; counts?: Record<string, number> }) {
  const entries = Object.entries(counts ?? {});
  return (
    <div className="card">
      <h3>{title}</h3>
      {entries.length === 0 ? <p className="muted">No orders yet.</p> : entries.map(([s, n]) => <p key={s}><Pill value={s} /> {n}</p>)}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RoleGate roles={["patient", "pharmacist", "admin"]}>
      <Dashboard />
    </RoleGate>
  );
}

function Dashboard() {
  const { data, error, loading } = useApi<Dash>("/dashboard");
  return (
    <>
      <h1>Dashboard{data?.pharmacy ? ` — ${data.pharmacy}` : ""}</h1>
      <Feedback loading={loading} error={error} />
      {data && data.role === "patient" && (
        <>
          <div className="grid">
            <Statuses title="My orders" counts={data.my_orders_by_status} />
            <Stat label="Open medicine shortages (demo data)" value={data.open_shortages} />
          </div>
          <p><Link href="/search">Search for a medicine</Link> · <Link href="/orders">My orders</Link></p>
        </>
      )}
      {data && data.role === "pharmacist" && (
        <>
          <div className="grid">
            <Statuses title="Orders at my pharmacy" counts={data.orders_by_status} />
            <Stat label="Open low-stock alerts" value={data.open_low_stock_alerts} />
            <Stat label="Open shortages (demo data)" value={data.open_shortages} />
          </div>
          <p><Link href="/orders">Review orders</Link> · <Link href="/inventory">Inventory &amp; alerts</Link></p>
        </>
      )}
      {data && data.role === "admin" && (
        <>
          <div className="grid">
            <Statuses title="All orders" counts={data.orders_by_status} />
            <Stat label="Open low-stock alerts" value={data.open_low_stock_alerts} />
            <Stat label="Open shortages" value={data.open_shortages} />
            <Stat label="Outbox rows not yet in MongoDB" value={data.sync_pending} />
            <Stat label="Users" value={data.users} />
          </div>
          <p><Link href="/admin">Catalog, shortages, users, SQL Demo</Link> · <Link href="/feed-lab">Feed Lab</Link></p>
        </>
      )}
    </>
  );
}
