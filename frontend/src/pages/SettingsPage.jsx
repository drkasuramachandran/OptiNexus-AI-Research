import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { PageHeader, Panel, SourceBadge } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const NAMES = { openalex: "OpenAlex", crossref: "Crossref", arxiv: "arXiv", pubmed: "PubMed" };

export default function SettingsPage() {
  const { user, setUser } = useAuth();
  const [s, setS] = useState(null);
  const [name, setName] = useState(user?.name || "");
  useEffect(() => { api.get("/settings").then((r) => setS(r.data)); }, []);

  const update = async (body) => {
    try { setS((await api.put("/settings", body)).data); toast.success("Settings saved"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const saveName = async () => {
    try { setUser((await api.put("/auth/profile", { name })).data); toast.success("Profile updated"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  if (!s) return <div className="text-muted-foreground">Loading…</div>;

  return (
    <div className="max-w-3xl">
      <PageHeader title="Settings" />
      <div className="space-y-6">
        <Panel>
          <h3 className="font-semibold mb-1">AI model</h3>
          <p className="text-sm text-muted-foreground mb-3">Used for profiles, Q&A and the assistant.</p>
          <Select value={s.model} onValueChange={(v) => update({ model: v })}>
            <SelectTrigger className="w-72" data-testid="model-select"><SelectValue /></SelectTrigger>
            <SelectContent>{s.models.map((m) => <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>)}</SelectContent>
          </Select>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Literature sources</h3>
          <div className="space-y-3">
            {Object.entries(NAMES).map(([k, label]) => (
              <div key={k} className="flex items-center justify-between">
                <SourceBadge s={label} />
                <Switch data-testid={`source-toggle-${k}`} checked={s.sources[k] !== false} onCheckedChange={(v) => update({ sources: { ...s.sources, [k]: v } })} />
              </div>
            ))}
          </div>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">API key status</h3>
          <div className="divide-y">
            {s.keys.map((k) => (
              <div key={k.key} className="flex items-center justify-between py-2.5 gap-4">
                <div><div className="font-mono text-sm">{k.key}</div><div className="text-xs text-muted-foreground">{k.purpose}</div></div>
                <span data-testid={`key-status-${k.key}`} className={`text-xs px-2 py-0.5 rounded border ${k.status === "configured" ? "text-emerald-600 dark:text-emerald-400 border-emerald-500/40" : k.required ? "text-destructive border-destructive/40" : "text-muted-foreground"}`}>{k.status}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-3">Keys are stored server-side as environment variables and are never displayed.</p>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Profile</h3>
          <div className="text-sm text-muted-foreground mb-2">{user?.email}</div>
          <div className="flex gap-2"><Input data-testid="profile-name-input" value={name} onChange={(e) => setName(e.target.value)} className="max-w-xs" />
            <Button onClick={saveName} data-testid="profile-save-button">Save</Button></div>
        </Panel>
      </div>
    </div>
  );
}
