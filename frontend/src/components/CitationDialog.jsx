import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, ShieldCheck, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, errMsg } from "@/lib/api";

const STYLES = ["APA", "IEEE", "Vancouver", "Harvard", "BibTeX", "RIS"];

const Verification = ({ v }) => (
  <div className="mt-4 text-sm" data-testid="verification-result">
    <div className={`font-medium ${v.status === "verified" ? "text-emerald-600 dark:text-emerald-400" : v.status === "mismatch" ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}`} data-testid="verification-status">
      {v.status.replace("_", " ").toUpperCase()} — {v.message}
    </div>
    {v.checks.length > 0 && (
      <table className="w-full mt-2 text-xs border">
        <thead><tr className="bg-muted"><th className="p-1.5 text-left">Field</th><th className="p-1.5 text-left">Stored</th><th className="p-1.5 text-left">Crossref</th><th className="p-1.5" /></tr></thead>
        <tbody>{v.checks.map((c) => (
          <tr key={c.field} className="border-t" data-testid={`verify-row-${c.field}`}>
            <td className="p-1.5">{c.field}</td><td className="p-1.5">{String(c.stored ?? "—")}</td><td className="p-1.5">{String(c.crossref ?? "—")}</td>
            <td className="p-1.5">{c.match === null ? <span className="text-muted-foreground">n/a</span> : c.match ? <CheckCircle2 size={14} className="text-emerald-500" /> : <XCircle size={14} className="text-amber-500" />}</td>
          </tr>))}</tbody>
      </table>
    )}
  </div>
);

export const CitationDialog = ({ paper, onClose }) => {
  const [data, setData] = useState(null);
  const [style, setStyle] = useState("APA");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(`/papers/${paper.id}/citations`).then((r) => setData(r.data)); }, [paper.id]);
  const verify = async () => {
    setBusy(true);
    try { const r = await api.post(`/papers/${paper.id}/verify`); setData({ ...data, verification: r.data }); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="citation-dialog">
        <DialogHeader><DialogTitle>Cite this paper</DialogTitle></DialogHeader>
        <Tabs value={style} onValueChange={setStyle}>
          <TabsList className="flex-wrap h-auto">{STYLES.map((s) => <TabsTrigger key={s} value={s} data-testid={`cite-style-${s}`}>{s}</TabsTrigger>)}</TabsList>
        </Tabs>
        <pre className="whitespace-pre-wrap text-sm bg-muted rounded-md p-3 font-mono min-h-[80px]" data-testid="citation-text">{data?.formats[style] || "Loading…"}</pre>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => { navigator.clipboard.writeText(data.formats[style]); toast.success("Copied"); }} disabled={!data} data-testid="copy-formatted-citation"><Copy size={14} className="mr-1" />Copy</Button>
          <Button size="sm" variant="outline" onClick={verify} disabled={busy} data-testid="verify-doi-button">{busy ? <Loader2 size={14} className="mr-1 animate-spin" /> : <ShieldCheck size={14} className="mr-1" />}Verify via Crossref DOI</Button>
        </div>
        {data?.verification && <Verification v={data.verification} />}
      </DialogContent>
    </Dialog>
  );
};
