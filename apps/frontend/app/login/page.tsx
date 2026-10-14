"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, saveSession, User } from "@/lib/api";
import { Emblem, ErrorText, PrimaryButton, Rule } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ access_token: string; user: User }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      saveSession(result.access_token, result.user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-ink p-12 text-husk-100 lg:flex">
        <Emblem className="pointer-events-none absolute -right-48 top-1/2 h-[560px] w-[560px] -translate-y-1/2 text-gold-500/[0.08]" />
        <div className="relative flex items-center gap-3">
          <Emblem className="h-12 w-12 text-gold-400" />
          <div className="eyebrow text-sm text-gold-300">Trung Nguyên Legend</div>
        </div>
        <div className="relative max-w-md">
          <p className="font-display text-3xl font-semibold leading-snug text-white">The energy coffee that changes life</p>
          <p className="mt-2 text-sm text-gold-300">Cà phê năng lượng · Cà phê đổi đời</p>
          <Rule className="my-6 max-w-[220px]" />
          <p className="text-sm leading-6 text-husk-300">AI watches every camera on the factory floor and raises the alert. People decide what each alert means.</p>
        </div>
        <div className="relative text-xs text-husk-500">Factory safety & compliance · Proof of concept</div>
      </section>
      <div className="grid place-items-center px-4 py-10">
        <form onSubmit={submit} className="panel w-full max-w-md border-t-2 border-t-gold-500 p-8 shadow-[0_10px_28px_rgba(42,30,21,.08)]">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <Emblem className="h-10 w-10 text-gold-600" />
            <div className="eyebrow text-gold-700">Trung Nguyên Legend</div>
          </div>
          <div className="eyebrow text-gold-700">Coffee factory POC</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">AI Safety & Compliance Monitoring</h1>
          <p className="mt-2 text-sm text-bark-600">Sign in to review cameras, zones, and safety alerts.</p>
          <div className="mt-6 space-y-3">
            <label className="block text-sm font-medium">Username<input className="mt-1" value={username} onChange={(e) => setUsername(e.target.value)} /></label>
            <label className="block text-sm font-medium">Password<input className="mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
            {error ? <ErrorText>{error}</ErrorText> : null}
            <PrimaryButton type="submit" disabled={busy} className="w-full py-2.5">{busy ? "Signing in…" : "Sign in"}</PrimaryButton>
          </div>
          <div className="mt-6 rounded-lg border border-line bg-paper p-3 font-mono text-xs leading-5 text-bark-600">
            <div>admin / admin123 — configure cameras, zones, and rules</div>
            <div>safety / safety123 — review incidents</div>
            <div>viewer / viewer123 — view only</div>
          </div>
        </form>
      </div>
    </div>
  );
}
