import React, { createContext, useContext, useEffect, useState } from "react";
import { api, setToken as setApiToken, getToken } from "../../api/client";

type User = { sub: string; role: "user" | "clinician" | "admin" } | null;
type Ctx = {
  user: User;
  login(u: string, p: string): Promise<void>;
  logout(): void;
};

const C = createContext<Ctx>(null as any);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User>(null);

  useEffect(() => {
    // Check if we have a token on mount
    const token = getToken();
    if (token) {
      // For demo, assume logged in if token exists
      // In production, decode JWT or call /auth/me endpoint
      setUser({ sub: "user", role: "user" });
    }
  }, []);

  async function login(username: string, password: string) {
    const r = await api.post("/auth/login", { username, password });
    const tok = r.data?.token;
    if (!tok) throw new Error("No token");
    setApiToken(tok);
    // Set user based on username for demo
    const role = username.includes("clinician") ? "clinician" : "user";
    setUser({ sub: username, role });
  }

  function logout() {
    setApiToken(null);
    setUser(null);
  }

  return <C.Provider value={{ user, login, logout }}>{children}</C.Provider>;
}

export const useAuth = () => useContext(C);