"use client";
import type { ReactNode } from "react";
import { SAFETY_NOTICE } from "@/lib/api";

export function SafetyNotice({ compact = false }: { compact?: boolean }) {
  return (
    <p className={compact ? "safety compact" : "safety"} role="note">
      <strong>Safety notice.</strong> {SAFETY_NOTICE}
    </p>
  );
}

export function Pill({ value }: { value: string }) {
  const cls = value.toLowerCase().replace(/[^a-z]+/g, "-");
  return <span className={`pill pill-${cls}`}>{value}</span>;
}

export function Feedback({ loading, error, success }: { loading?: boolean; error?: string | null; success?: string | null }) {
  return (
    <>
      {loading && <p className="muted" aria-live="polite">Loading…</p>}
      {error && <p className="alert error" role="alert">{error}</p>}
      {success && <p className="alert ok" role="status">{success}</p>}
    </>
  );
}

export function Table({ columns, rows, empty = "Nothing to show." }: { columns: { key: string; label: string; render?: (row: Record<string, unknown>) => ReactNode }[]; rows: Record<string, unknown>[]; empty?: string }) {
  if (!rows.length) return <p className="muted">{empty}</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(r) : String(r[c.key] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function confirmAction(message: string): boolean {
  return typeof window !== "undefined" && window.confirm(message);
}
