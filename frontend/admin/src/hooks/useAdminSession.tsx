"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import api from "@/lib/api";
import { AdminSession } from "@/lib/types";

export const PUBLIC_ADMIN_PATHS = ["/login"];

type AdminSessionContextValue = {
  admin: AdminSession | null;
  loading: boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AdminSessionContext = createContext<AdminSessionContextValue | null>(null);

export function AdminSessionProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [admin, setAdmin] = useState<AdminSession | null>(null);
  const [loading, setLoading] = useState(true);

  const loadSession = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const response = await api.get<AdminSession>("/admin/auth/me", { signal });
      setAdmin(response.data);
    } catch {
      setAdmin(null);
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadSession(controller.signal);
    return () => controller.abort();
  }, [loadSession, pathname]);

  const logout = useCallback(async () => {
    try {
      await api.post("/admin/auth/logout");
    } catch {}
    setAdmin(null);
    router.replace("/login");
  }, [router]);

  const refresh = useCallback(async () => {
    await loadSession();
  }, [loadSession]);

  const value = useMemo(
    () => ({
      admin,
      loading,
      logout,
      refresh,
    }),
    [admin, loading, logout, refresh],
  );

  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>;
}

export function useAdminSession() {
  const context = useContext(AdminSessionContext);
  if (!context) {
    throw new Error("useAdminSession must be used within an AdminSessionProvider");
  }
  return context;
}
