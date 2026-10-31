"use client";
import { useCallback, useEffect, useState } from "react";

export const SAFETY_NOTICE =
  "This is an educational demonstration. Candidate matches are not medical advice or an authorization to substitute a medicine. A qualified pharmacist must verify the medicine and applicable prescription requirements before any substitution or sale.";

export type Role = "patient" | "pharmacist" | "admin";
export type User = { id: number; email: string; full_name: string; role: Role; pharmacy_id: number | null };

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** All calls go to /api/* on the Next origin (proxied to FastAPI); the session is an httpOnly cookie. */
export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: init.method ?? (init.body !== undefined ? "POST" : "GET"),
    headers: init.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    credentials: "same-origin",
  });
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const d = data as { detail?: unknown } | null;
    const detail = typeof d?.detail === "string" ? d.detail : d?.detail ? JSON.stringify(d.detail) : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

/** GET with loading / error state and a reload function. Pass path=null to skip. */
export function useApi<T>(path: string | null) {
  const [tick, setTick] = useState(0);
  const key = `${path}#${tick}`;
  const [res, setRes] = useState<{ key: string; data: T | null; error: string | null } | null>(null);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  useEffect(() => {
    if (path === null) return;
    let alive = true;
    api<T>(path)
      .then((d) => alive && setRes({ key, data: d, error: null }))
      .catch((e: Error) => alive && setRes({ key, data: null, error: e.message }));
    return () => {
      alive = false;
    };
  }, [path, key]);
  const settled = res?.key === key;
  return {
    data: res?.data ?? null, // previous data stays visible while a reload is in flight
    error: settled ? res.error : null,
    loading: path !== null && !settled,
    reload,
  };
}

export function fmtDate(s?: string | null) {
  if (!s) return "";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString();
}
