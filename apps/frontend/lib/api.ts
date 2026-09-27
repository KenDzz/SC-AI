export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type User = { id: string; username: string; full_name: string; role: "ADMIN" | "SAFETY_MANAGER" | "VIEWER" };

export type Camera = {
  id: string;
  factory_id: string;
  code: string;
  name: string;
  area: string;
  stream_type: "RTSP" | "FILE";
  stream_url: string | null;
  enabled: boolean;
  ai_fps: number;
  assigned_worker: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Zone = {
  id: string;
  factory_id: string;
  camera_id: string;
  name: string;
  zone_type: string;
  polygon: number[][];
};

export type Rule = {
  id: string;
  factory_id: string;
  camera_id: string;
  zone_id: string;
  zone_name?: string | null;
  camera_name?: string | null;
  name: string;
  event_type: string;
  condition_type: string;
  min_duration_ms: number;
  cooldown_ms: number;
  grace_ms: number;
  severity: string;
  enabled: boolean;
};

export type Incident = {
  id: string;
  factory_id: string;
  camera_id: string;
  camera_name?: string | null;
  zone_id: string | null;
  zone_name?: string | null;
  rule_id: string | null;
  rule_name?: string | null;
  event_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  track_id: string | null;
  confidence: number | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  snapshot_uri: string | null;
  clip_uri: string | null;
  model_name: string | null;
  model_version: string | null;
  ai_mode: string | null;
  created_at: string;
  updated_at: string;
};

export function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || "";
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function saveSession(token: string, user: User) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

function errorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return fallback;
  const parts = detail
    .map((item) => {
      if (!item || typeof item !== "object") return "";
      const row = item as { loc?: unknown; msg?: unknown };
      const loc = Array.isArray(row.loc) ? row.loc.filter((part) => part !== "body").join(".") : "";
      const msg = typeof row.msg === "string" ? row.msg : "";
      if (loc && msg) return `${loc}: ${msg}`;
      return msg;
    })
    .filter(Boolean);
  return parts.length ? parts.join("; ") : fallback;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Accept", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401 && !path.startsWith("/api/auth/login")) {
    clearSession();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Please sign in again");
  }
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = errorMessage(body, message);
    } catch {
      /* response had no JSON body */
    }
    throw new Error(message || "Request failed");
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return response.json();
  return (await response.blob()) as T;
}

export async function imageUrl(path: string) {
  const blob = await api<Blob>(path);
  return URL.createObjectURL(blob);
}
