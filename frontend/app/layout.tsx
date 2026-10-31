import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { Header } from "@/components/Header";
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
        <AuthProvider>
          <Header />
          <main className="container">{children}</main>
          <footer className="footer">
            <SafetyNotice compact />
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
