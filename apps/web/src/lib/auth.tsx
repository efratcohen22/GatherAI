import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, configureApi, hasToken } from "./api";
import type { Me } from "./types";

interface Config { auth_mode: "local" | "supabase"; ai_live: boolean; environment: string }
interface AuthState {
  config: Config | null;
  me: Me | null;
  loading: boolean;
  login(email: string, password: string): Promise<void>;
  signup(email: string, password: string, displayName: string): Promise<void>;
  logout(): Promise<void>;
  resetPassword(email: string): Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);
const KEY = "gatherai.local_token";

function readToken(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
function writeToken(value: string | null) {
  try { if (value) localStorage.setItem(KEY, value); else localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
}

let supabase: SupabaseClient | null = null;
function getSupabase(): SupabaseClient {
  if (!supabase) supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_ANON_KEY);
  return supabase;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<Config | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => setMe(await api<Me>("/api/auth/me")), []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const cfg = await api<Config>("/api/config");
        if (!active) return;
        setConfig(cfg);
        configureApi(
          async () => cfg.auth_mode === "local" ? readToken() : (await getSupabase().auth.getSession()).data.session?.access_token ?? null,
          () => { writeToken(null); setMe(null); },
        );
        if (await hasToken()) await loadMe().catch(() => undefined);
      } catch { /* server unreachable: public pages still render */ }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [loadMe]);

  const value = useMemo<AuthState>(() => ({
    config, me, loading,
    async login(email, password) {
      if (config?.auth_mode === "supabase") {
        const { error } = await getSupabase().auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        writeToken((await api<{ access_token: string }>("/api/auth/local/login", "POST", { email, password })).access_token);
      }
      await loadMe();
    },
    async signup(email, password, displayName) {
      if (config?.auth_mode === "supabase") {
        const { error } = await getSupabase().auth.signUp({ email, password, options: { data: { display_name: displayName } } });
        if (error) throw error;
      } else {
        writeToken((await api<{ access_token: string }>("/api/auth/local/signup", "POST", { email, password, display_name: displayName })).access_token);
      }
      await loadMe();
    },
    async logout() {
      if (config?.auth_mode === "supabase") await getSupabase().auth.signOut();
      writeToken(null);
      setMe(null);
    },
    async resetPassword(email) {
      if (config?.auth_mode !== "supabase") throw new Error("Password reset needs email delivery, which is not available in local development mode.");
      const { error } = await getSupabase().auth.resetPasswordForEmail(email);
      if (error) throw error;
    },
  }), [config, me, loading, loadMe]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const value = useContext(Ctx);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
