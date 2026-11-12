import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!localStorage.getItem("onx_token")) return setUser(false);
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => setUser(false));
  }, []);

  const signIn = (data) => {
    localStorage.setItem("onx_token", data.token);
    setUser(data.user);
  };
  const logout = () => {
    localStorage.removeItem("onx_token");
    setUser(false);
  };
  return <AuthCtx.Provider value={{ user, setUser, signIn, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
