"use client";

import { useEffect, useRef } from "react";
import type { Incident } from "@/lib/api";

// One in-page channel for incident changes. The shell feeds it from the server event stream;
// the review drawer feeds it after a decision so pages refresh even when the stream is down.
type Listener = (incident: Incident | null) => void;
const listeners = new Set<Listener>();

export function emitIncident(incident: Incident | null) {
  listeners.forEach((listener) => listener(incident));
}

// With delayMs, a burst of events triggers the listener once, delayMs after the last one.
export function useIncidentEvents(listener: Listener, delayMs = 0) {
  const latest = useRef(listener);
  latest.current = listener;
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const relay: Listener = (incident) => {
      if (!delayMs) return latest.current(incident);
      clearTimeout(timer);
      timer = setTimeout(() => latest.current(incident), delayMs);
    };
    listeners.add(relay);
    return () => {
      clearTimeout(timer);
      listeners.delete(relay);
    };
  }, [delayMs]);
}
