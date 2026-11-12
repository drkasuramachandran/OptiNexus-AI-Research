import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo, TAGLINE } from "@/components/Logo";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { signIn } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const { data } = await api.post(isLogin ? "/auth/login" : "/auth/register", isLogin ? { email: f.email, password: f.password } : f);
      signIn(data);
      nav("/");
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  };
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-[#071226] text-white grid-bg relative overflow-hidden">
        <div className="flex items-center gap-3"><Logo size={40} /><span className="font-display text-xl font-semibold">OptiNexus AI</span></div>
        <div className="fade-up">
          <h1 className="text-5xl font-semibold leading-tight max-w-md">{TAGLINE}</h1>
          <p className="mt-5 text-slate-300 max-w-md">Search four scholarly indexes at once, analyse your PDFs with page-cited answers, and reason across your project's evidence — without fabricated references.</p>
        </div>
        <div className="text-xs text-slate-400 font-mono">OpenAlex · Crossref · arXiv · PubMed</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5 fade-up" data-testid={`${mode}-form`}>
          <div className="lg:hidden flex items-center gap-3 mb-4"><Logo /><div><div className="font-display font-semibold">OptiNexus AI</div><div className="text-xs text-muted-foreground">{TAGLINE}</div></div></div>
          <div>
            <h2 className="text-2xl font-semibold">{isLogin ? "Welcome back" : "Create your workspace"}</h2>
            <p className="text-sm text-muted-foreground mt-1">{isLogin ? "Sign in to continue your research." : "Your projects and papers stay private to your account."}</p>
          </div>
          {!isLogin && (
            <div className="space-y-1.5"><Label>Name</Label><Input data-testid="register-name-input" value={f.name} onChange={set("name")} required /></div>
          )}
          <div className="space-y-1.5"><Label>Email</Label><Input data-testid={`${mode}-email-input`} type="email" value={f.email} onChange={set("email")} required /></div>
          <div className="space-y-1.5"><Label>Password</Label><Input data-testid={`${mode}-password-input`} type="password" minLength={8} value={f.password} onChange={set("password")} required /></div>
          {err && <div data-testid="auth-error" className="text-sm text-destructive">{err}</div>}
          <Button data-testid={`${mode}-submit-button`} className="w-full" disabled={busy}>{busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}</Button>
          <p className="text-sm text-muted-foreground text-center">
            {isLogin ? "New here? " : "Already have an account? "}
            <Link data-testid="auth-switch-link" className="text-primary hover:underline" to={isLogin ? "/register" : "/login"}>{isLogin ? "Create an account" : "Sign in"}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
