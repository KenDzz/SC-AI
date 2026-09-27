import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Safety & Compliance Monitoring",
  description: "Factory safety monitoring proof of concept",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
