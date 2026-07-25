"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { User, getMe } from "./api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  setAuth: () => {},
  logout: () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const setAuth = useCallback((t: string, u: User) => {
    setToken(t);
    setUser(u);
    localStorage.setItem("adfeed_token", t);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("adfeed_token");
  }, []);

  const refresh = useCallback(async () => {
    const t = localStorage.getItem("adfeed_token");
    if (!t) {
      setLoading(false);
      return;
    }
    try {
      const u = await getMe(t);
      setToken(t);
      setUser(u);
    } catch {
      localStorage.removeItem("adfeed_token");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ user, token, loading, setAuth, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
