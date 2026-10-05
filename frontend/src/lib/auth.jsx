import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anon, obj = user
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (e) {
      setUser(false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function login(email, password) {
    const { data } = await api.post("/auth/login", { email, password });
    if (data.token) localStorage.setItem("acorde_token", data.token);
    setUser(data.user);
    return data.user;
  }

  async function logout() {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("acorde_token");
    setUser(false);
  }

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
