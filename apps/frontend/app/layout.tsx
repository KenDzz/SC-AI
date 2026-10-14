import "./globals.css";
import type { Metadata } from "next";
import { Be_Vietnam_Pro, Cinzel, JetBrains_Mono } from "next/font/google";
import Providers from "@/components/providers";

// Be Vietnam Pro carries the UI and every user-entered name (full Vietnamese subset).
// Cinzel stands in for the brand's Trajan Pro 3, but has no Vietnamese glyphs: see displayFont() in lib/labels.ts.
// JetBrains Mono sets times, codes and measurements.
const sans = Be_Vietnam_Pro({ subsets: ["latin", "vietnamese"], weight: ["400", "500", "600", "700"], variable: "--font-sans", display: "swap" });
const display = Cinzel({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-display", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "AI Safety & Compliance Monitoring · Trung Nguyên Legend",
  description: "Factory safety monitoring proof of concept",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
