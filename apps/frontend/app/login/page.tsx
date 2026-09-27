"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, saveSession, User } from "@/lib/api";
import { ErrorText, PrimaryButton } from "@/components/ui";

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
    <div className="grid min-h-screen place-items-center px-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-2xl border border-line bg-white p-8 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-pine">Coffee Factory POC</div>
        <h1 className="mt-2 text-2xl font-semibold">AI Safety & Compliance Monitoring</h1>
        <p className="mt-2 text-sm text-slate-600">Sign in to review cameras, zones, and safety alerts.</p>
        <div className="mt-6 space-y-3">
          <label className="block text-sm font-medium">Username<input className="mt-1" value={username} onChange={(e) => setUsername(e.target.value)} /></label>
          <label className="block text-sm font-medium">Password<input className="mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          {error ? <ErrorText>{error}</ErrorText> : null}
          <PrimaryButton type="submit" disabled={busy} className="w-full">{busy ? "Signing in…" : "Sign in"}</PrimaryButton>
        </div>
        <div className="mt-6 rounded-lg bg-paper p-3 text-xs leading-5 text-slate-600">
          <div>admin / admin123 — configure cameras, zones, and rules</div>
          <div>safety / safety123 — review incidents</div>
          <div>viewer / viewer123 — view only</div>
        </div>
      </form>
    </div>
  );
}
