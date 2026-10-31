"use client";
import { useState, type FormEvent } from "react";
import { RoleGate } from "@/lib/auth";
import { api, fmtDate, useApi } from "@/lib/api";
import { Feedback, Pill, Table, confirmAction } from "@/components/ui";

type Tab = "catalog" | "pharmacies" | "shortages" | "users" | "sql";

export default function AdminPage() {
  return (
    <RoleGate roles={["admin"]}>
      <Admin />
    </RoleGate>
  );
}

function Admin() {
  const [tab, setTab] = useState<Tab>("catalog");
  const tabs: [Tab, string][] = [["catalog", "Catalog"], ["pharmacies", "Pharmacies"], ["shortages", "Shortages"], ["users", "Users & assignments"], ["sql", "SQL Demo"]];
  return (
    <>
      <h1>Admin</h1>
      <div className="tabs" role="tablist">
        {tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "catalog" && <Catalog />}
      {tab === "pharmacies" && <Pharmacies />}
      {tab === "shortages" && <Shortages />}
      {tab === "users" && <Users />}
      {tab === "sql" && <SqlDemo />}
    </>
  );
}

type Med = { id: number; name: string; brand: string; category: string; composition: string; dosage_form: string; is_active: number; requires_prescription: number; substitution_allowed: number };

type IngRow = { ingredient_id: number; strength_mg: number };
type MedForm = { name: string; brand: string; category_id: number; dosage_form: string; route: string; release_type: string; strength_basis: string; requires_prescription: boolean; substitution_allowed: boolean; is_active: boolean; ingredients: IngRow[] };
const EMPTY: MedForm = { name: "", brand: "", category_id: 0, dosage_form: "tablet", route: "oral", release_type: "immediate", strength_basis: "per tablet", requires_prescription: false, substitution_allowed: true, is_active: true, ingredients: [{ ingredient_id: 0, strength_mg: 0 }] };

function Catalog() {
  const meds = useApi<Med[]>("/medicines?include_inactive=true");
  const cats = useApi<{ id: number; path: string }[]>("/categories/tree");
  const ings = useApi<{ id: number; name: string }[]>("/ingredients");
  const [f, setF] = useState<MedForm>(EMPTY);
  const [editId, setEditId] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  async function save(e: FormEvent) {
    e.preventDefault();
    setMsg({});
    try {
      if (editId === null) {
        await api("/medicines", { body: f });
        setMsg({ ok: "Medicine created (INSERT)." });
      } else {
        await api(`/medicines/${editId}`, { method: "PUT", body: f });
        setMsg({ ok: `Medicine #${editId} updated (UPDATE).` });
      }
      setEditId(null);
      setF(EMPTY);
      meds.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function startEdit(m: Med) {
    setMsg({});
    try {
      const d = await api<MedForm & { ingredients: { ingredient_id: number; strength_mg: number | string }[] }>(`/medicines/${m.id}`);
      setF({
        name: d.name, brand: d.brand, category_id: d.category_id, dosage_form: d.dosage_form, route: d.route, release_type: d.release_type,
        strength_basis: d.strength_basis, requires_prescription: !!d.requires_prescription, substitution_allowed: !!d.substitution_allowed,
        is_active: !!d.is_active, ingredients: d.ingredients.map((i) => ({ ingredient_id: i.ingredient_id, strength_mg: Number(i.strength_mg) })),
      });
      setEditId(m.id);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function deactivate(m: Med) {
    if (!confirmAction(`Deactivate ${m.name}? (soft delete: is_active = 0; stock and order history are kept)`)) return;
    try {
      await api(`/medicines/${m.id}`, { method: "DELETE" });
      setMsg({ ok: `${m.name} deactivated.` });
      meds.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  const setIng = (i: number, patch: Partial<IngRow>) => setF({ ...f, ingredients: f.ingredients.map((r, k) => (k === i ? { ...r, ...patch } : r)) });

  return (
    <>
      <form className="card" onSubmit={save}>
        <h2>{editId === null ? "Add medicine" : `Edit medicine #${editId}`}</h2>
        <div className="row">
          <label>Name<input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
          <label>Brand<input required value={f.brand} onChange={(e) => setF({ ...f, brand: e.target.value })} /></label>
          <label>Category
            <select required value={f.category_id} onChange={(e) => setF({ ...f, category_id: Number(e.target.value) })}>
              <option value={0}>— choose —</option>
              {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.path}</option>)}
            </select>
          </label>
          <label>Form
            <select value={f.dosage_form} onChange={(e) => setF({ ...f, dosage_form: e.target.value })}>
              {["tablet", "capsule", "syrup", "injection", "ointment"].map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label>Strength basis
            <select value={f.strength_basis} onChange={(e) => setF({ ...f, strength_basis: e.target.value })}>
              {["per tablet", "per capsule", "per 5 ml", "per ml", "per gram"].map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label>Release
            <select value={f.release_type} onChange={(e) => setF({ ...f, release_type: e.target.value })}>
              <option>immediate</option><option>extended</option>
            </select>
          </label>
          <label><span>Rx only</span><input type="checkbox" checked={f.requires_prescription} onChange={(e) => setF({ ...f, requires_prescription: e.target.checked })} /></label>
          <label><span>Substitution allowed</span><input type="checkbox" checked={f.substitution_allowed} onChange={(e) => setF({ ...f, substitution_allowed: e.target.checked })} /></label>
          <label><span>Active</span><input type="checkbox" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /></label>
        </div>
        <h3>Composition (medicine_ingredients rows)</h3>
        {f.ingredients.map((r, i) => (
          <div className="row" key={i}>
            <label>Ingredient
              <select required value={r.ingredient_id} onChange={(e) => setIng(i, { ingredient_id: Number(e.target.value) })}>
                <option value={0}>— choose —</option>
                {ings.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </label>
            <label>Strength (mg)<input type="number" min={0.001} step="any" required value={r.strength_mg || ""} onChange={(e) => setIng(i, { strength_mg: Number(e.target.value) })} /></label>
            {f.ingredients.length > 1 && <button type="button" className="secondary" onClick={() => setF({ ...f, ingredients: f.ingredients.filter((_, k) => k !== i) })}>Remove</button>}
          </div>
        ))}
        <div className="row">
          <button type="button" className="secondary" onClick={() => setF({ ...f, ingredients: [...f.ingredients, { ingredient_id: 0, strength_mg: 0 }] })}>Add ingredient (combination product)</button>
          <button type="submit">{editId === null ? "Create" : "Save changes"}</button>
          {editId !== null && <button type="button" className="secondary" onClick={() => { setEditId(null); setF(EMPTY); }}>Cancel edit</button>}
        </div>
        <Feedback error={msg.err} success={msg.ok} />
      </form>
      <Feedback loading={meds.loading} error={meds.error} />
      <Table
        columns={[
          { key: "id", label: "#" }, { key: "name", label: "Medicine" }, { key: "brand", label: "Brand" }, { key: "composition", label: "Composition" }, { key: "category", label: "Category" },
          { key: "is_active", label: "Status", render: (r) => <Pill value={r.is_active ? "Active" : "Inactive"} /> },
          { key: "act", label: "", render: (r) => (
            <>
              <button className="secondary" onClick={() => startEdit(r as unknown as Med)}>Edit</button>{" "}
              {r.is_active ? <button className="danger" onClick={() => deactivate(r as unknown as Med)}>Deactivate</button> : null}
            </>) },
        ]}
        rows={(meds.data ?? []) as unknown as Record<string, unknown>[]}
      />
    </>
  );
}

type Pharm = { id: number; name: string; city: string; address: string | null };

function Pharmacies() {
  const list = useApi<Pharm[]>("/pharmacies");
  const [f, setF] = useState({ name: "", city: "", address: "" });
  const [editId, setEditId] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  async function save(e: FormEvent) {
    e.preventDefault();
    setMsg({});
    try {
      const body = { name: f.name, city: f.city, address: f.address || null };
      if (editId === null) await api("/pharmacies", { body });
      else await api(`/pharmacies/${editId}`, { method: "PUT", body });
      setMsg({ ok: editId === null ? "Pharmacy created (INSERT)." : "Pharmacy updated (UPDATE)." });
      setEditId(null);
      setF({ name: "", city: "", address: "" });
      list.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  return (
    <>
      <form className="card row" onSubmit={save}>
        <label>Name<input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
        <label>City<input required value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></label>
        <label>Address<input value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></label>
        <button type="submit">{editId === null ? "Add pharmacy" : "Save changes"}</button>
        {editId !== null && <button type="button" className="secondary" onClick={() => { setEditId(null); setF({ name: "", city: "", address: "" }); }}>Cancel</button>}
      </form>
      <Feedback loading={list.loading} error={list.error ?? msg.err} success={msg.ok} />
      <Table
        columns={[
          { key: "id", label: "#" }, { key: "name", label: "Name" }, { key: "city", label: "City" }, { key: "address", label: "Address" },
          { key: "act", label: "", render: (r) => <button className="secondary" onClick={() => { setEditId(Number(r.id)); setF({ name: String(r.name), city: String(r.city), address: String(r.address ?? "") }); }}>Edit</button> },
        ]}
        rows={(list.data ?? []) as unknown as Record<string, unknown>[]}
      />
    </>
  );
}

type Shortage = { id: number; medicine_name: string; status: string; severity: string; reported_at: string; note: string | null };

function Shortages() {
  const sh = useApi<Shortage[]>("/shortages");
  const meds = useApi<{ id: number; name: string }[]>("/medicines");
  const [medicine, setMedicine] = useState(0);
  const [severity, setSeverity] = useState("MEDIUM");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/shortages", { body: { medicine_id: medicine, severity, note: note || null } });
      setMsg({ ok: "Shortage entry added (synthetic demo data)." });
      sh.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function resolve(id: number) {
    if (!confirmAction("Mark this shortage as resolved?")) return;
    try {
      await api(`/shortages/${id}/resolve`, { method: "PATCH", body: {} });
      sh.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function remove(id: number) {
    if (!confirmAction("Permanently delete this shortage entry (SQL DELETE)?")) return;
    try {
      await api(`/shortages/${id}`, { method: "DELETE" });
      setMsg({ ok: "Shortage entry deleted." });
      sh.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  return (
    <>
      <p className="muted">Shortage entries are synthetic demo records (source = demo), not live or official shortage data.</p>
      <form className="card row" onSubmit={add}>
        <label>Medicine
          <select required value={medicine} onChange={(e) => setMedicine(Number(e.target.value))}>
            <option value={0}>— choose —</option>
            {meds.data?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <label>Severity
          <select value={severity} onChange={(e) => setSeverity(e.target.value)}><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select>
        </label>
        <label>Note<input value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} /></label>
        <button type="submit">Add</button>
      </form>
      <Feedback loading={sh.loading} error={sh.error ?? msg.err} success={msg.ok} />
      <Table
        columns={[
          { key: "medicine_name", label: "Medicine" }, { key: "status", label: "Status", render: (r) => <Pill value={String(r.status)} /> },
          { key: "severity", label: "Severity" }, { key: "reported_at", label: "Reported", render: (r) => fmtDate(String(r.reported_at)) }, { key: "note", label: "Note" },
          { key: "act", label: "", render: (r) => (<>{r.status === "OPEN" ? <button className="secondary" onClick={() => resolve(Number(r.id))}>Resolve</button> : null}{" "}<button className="danger" onClick={() => remove(Number(r.id))}>Delete</button></>) },
        ]}
        rows={(sh.data ?? []) as unknown as Record<string, unknown>[]}
      />
    </>
  );
}

type UserRow = { id: number; email: string; full_name: string; role: string; is_active: number; pharmacy_id: number | null; pharmacy_name: string | null };

function Users() {
  const users = useApi<UserRow[]>("/admin/users");
  const pharmacies = useApi<{ id: number; name: string }[]>("/pharmacies");
  const [f, setF] = useState({ email: "", full_name: "", role: "patient", password: "", pharmacy_id: 0 });
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  async function create(e: FormEvent) {
    e.preventDefault();
    setMsg({});
    try {
      await api("/admin/users", { body: { ...f, pharmacy_id: f.role === "pharmacist" ? f.pharmacy_id || null : null } });
      setMsg({ ok: "User created." });
      users.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function toggle(u: UserRow) {
    if (!confirmAction(`${u.is_active ? "Deactivate" : "Activate"} ${u.email}?`)) return;
    try {
      await api(`/admin/users/${u.id}/active`, { method: "PATCH", body: { is_active: !u.is_active } });
      users.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  async function assign(u: UserRow, pharmacy_id: number) {
    try {
      await api(`/admin/users/${u.id}/pharmacy`, { method: "PUT", body: { pharmacy_id } });
      setMsg({ ok: "Assignment updated." });
      users.reload();
    } catch (err) {
      setMsg({ err: (err as Error).message });
    }
  }

  return (
    <>
      <form className="card" onSubmit={create}>
        <h2>Create user</h2>
        <div className="row">
          <label>Email<input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
          <label>Full name<input required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
          <label>Role
            <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option>patient</option><option>pharmacist</option><option>admin</option></select>
          </label>
          {f.role === "pharmacist" && (
            <label>Pharmacy
              <select required value={f.pharmacy_id} onChange={(e) => setF({ ...f, pharmacy_id: Number(e.target.value) })}>
                <option value={0}>— choose —</option>
                {pharmacies.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
          )}
          <label>Password (min 8)<input type="password" minLength={8} required autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
          <button type="submit">Create</button>
        </div>
      </form>
      <Feedback loading={users.loading} error={users.error ?? msg.err} success={msg.ok} />
      <Table
        columns={[
          { key: "email", label: "Email" }, { key: "full_name", label: "Name" }, { key: "role", label: "Role", render: (r) => <Pill value={String(r.role)} /> },
          { key: "pharmacy_name", label: "Pharmacy", render: (r) => r.role === "pharmacist" ? (
            <select value={Number(r.pharmacy_id ?? 0)} onChange={(e) => assign(r as unknown as UserRow, Number(e.target.value))} aria-label="Assigned pharmacy">
              {pharmacies.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>) : "" },
          { key: "is_active", label: "Active", render: (r) => <Pill value={r.is_active ? "Active" : "Inactive"} /> },
          { key: "act", label: "", render: (r) => <button className="secondary" onClick={() => toggle(r as unknown as UserRow)}>{r.is_active ? "Deactivate" : "Activate"}</button> },
        ]}
        rows={(users.data ?? []) as unknown as Record<string, unknown>[]}
      />
    </>
  );
}

type Q = { name: string; file: string; purpose: string; why: string; expected: string; runnable: boolean; sql: string };

function SqlDemo() {
  const list = useApi<Q[]>("/admin/sql-demo");
  const [result, setResult] = useState<{ name: string; columns: string[]; rows: Record<string, unknown>[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function run(name: string) {
    setErr(null);
    try {
      setResult(await api(`/admin/sql-demo/${name}/run`, { method: "POST", body: {} }));
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <>
      <p className="muted">Only named, read-only queries from <code>database/sql/queries.sql</code> and <code>advanced.sql</code> can run here. No arbitrary SQL.</p>
      <Feedback loading={list.loading} error={list.error ?? err} />
      {list.data?.map((q) => (
        <div className="card" key={q.name}>
          <strong>{q.name}</strong> <span className="muted">({q.file})</span>
          <p>{q.purpose}</p>
          {q.why && <p className="muted"><em>Why it qualifies:</em> {q.why}</p>}
          <pre>{q.sql}</pre>
          {q.expected && <p className="muted">Expected: {q.expected}</p>}
          {q.runnable ? <button onClick={() => run(q.name)}>Run</button> : <span className="muted">Not runnable from the web (needs a request context) — see scripts/run_sql_demo.py</span>}
          {result?.name === q.name && (
            <Table columns={result.columns.map((c) => ({ key: c, label: c }))} rows={result.rows} empty="No rows." />
          )}
        </div>
      ))}
    </>
  );
}
