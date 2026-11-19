"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/api";

const NAV: { href: string; label: string; roles: Role[] }[] = [
  { href: "/dashboard", label: "Dashboard", roles: ["patient", "pharmacist", "admin"] },
  { href: "/search", label: "Search & availability", roles: ["patient", "pharmacist", "admin"] },
  { href: "/orders", label: "Orders", roles: ["patient", "pharmacist"] },
  { href: "/inventory", label: "Inventory & alerts", roles: ["pharmacist", "admin"] },
  { href: "/admin", label: "Admin", roles: ["admin"] },
];

export function Header() {
  const { user, logout } = useAuth();
  const path = usePathname();
  return (
    <header className="header">
      <div className="header-inner">
        <span className="brand">Medicine Substitution &amp; Shortage Finder</span>
        <span className="muted">{NAV.find((n) => path.startsWith(n.href))?.label}</span>
        {user && (
          <span className="who">
            {user.full_name} <span className={`pill pill-${user.role}`}>{user.role}</span>
            {user.pharmacy_id && <span>Pharmacy #{user.pharmacy_id}</span>}
            <button className="link" onClick={logout}>Log out</button>
          </span>
        )}
      </div>
    </header>
  );
}

export function Navigation() {
  const { user } = useAuth();
  const path = usePathname();
  return <aside className="sidebar">{user && <>
    <p className="nav-label">Workspace</p>
    <nav aria-label="Main">
      {NAV.filter((n) => n.roles.includes(user.role)).map((n) => (
        <Link key={n.href} href={n.href} aria-current={path.startsWith(n.href) ? "page" : undefined}>{n.label}</Link>
      ))}
    </nav>
  </>}</aside>;
}
