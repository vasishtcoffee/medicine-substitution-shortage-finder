import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { Header, Navigation } from "@/components/Header";
import { SafetyNotice } from "@/components/ui";
import "./globals.css";

export const metadata: Metadata = {
  title: "Medicine Substitution & Shortage Finder",
  description: "Educational demonstration: find in-stock medicines and pharmacist-verified composition matches.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <AuthProvider>
          <Header />
          <div className="app-shell">
            <Navigation />
            <main id="main-content" tabIndex={-1} className="container">{children}</main>
          </div>
          <footer className="footer">
            <SafetyNotice compact />
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
