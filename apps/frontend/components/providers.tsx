"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import IncidentDrawer from "@/components/incident-drawer";
import { Diamond } from "@/components/ui";

type Toast = { message: string; incidentId?: string };
type App = { toast: (message: string, incidentId?: string) => void; openIncident: (id: string) => void };

const AppContext = createContext<App>({ toast: () => undefined, openIncident: () => undefined });

export function useApp() {
  return useContext(AppContext);
}

export default function Providers({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const showToast = useCallback((message: string, id?: string) => {
    clearTimeout(timer.current);
    setToast({ message, incidentId: id });
    timer.current = setTimeout(() => setToast(null), 4500);
  }, []);
  useEffect(() => () => clearTimeout(timer.current), []);

  const value = useMemo(() => ({ toast: showToast, openIncident: setIncidentId }), [showToast]);

  return (
    <AppContext.Provider value={value}>
      {children}
      {incidentId ? <IncidentDrawer id={incidentId} onClose={() => setIncidentId(null)} onOpen={setIncidentId} toast={showToast} /> : null}
      <div aria-live="polite" className="fixed bottom-6 right-6 z-30">
        {toast ? (
          <div className="flex items-center gap-3.5 rounded-[10px] border border-gold-500/40 bg-ink py-3.5 pl-[18px] pr-4 text-husk-100 shadow-[0_14px_40px_rgba(23,17,12,.35)] motion-safe:animate-slide-in">
            <Diamond className="h-2 w-2 bg-gold-300" />
            <span className="text-[13.5px]">{toast.message}</span>
            {toast.incidentId ? (
              <button
                className="p-0 text-[13px] font-semibold text-gold-300 hover:text-gold-200"
                onClick={() => {
                  setIncidentId(toast.incidentId || null);
                  setToast(null);
                }}
              >
                Review →
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </AppContext.Provider>
  );
}
