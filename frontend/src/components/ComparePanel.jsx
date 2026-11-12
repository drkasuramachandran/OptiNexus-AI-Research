import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Download, Columns3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty } from "@/components/common";
import { api, errMsg } from "@/lib/api";

const LABELS = { objectives: "Objectives", methodology: "Methodology", instruments: "Instruments", parameters: "Parameters",
  conditions: "Conditions", results: "Results", limitations: "Limitations" };

const toCSV = (res) => {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const head = ["Paper", "Year", "Content used", ...res.fields.map((f) => LABELS[f])];
  const rows = res.rows.map((r) => [r.title, r.year, r.basis, ...res.fields.map((f) => r[f])]);
  return [head, ...rows].map((r) => r.map(esc).join(",")).join("\n");
};

export const downloadBlob = (blob, name) => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
};

export default function ComparePanel({ pid }) {
  const [papers, setPapers] = useState([]);
  const [sel, setSel] = useState([]);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  useEffect(() => { api.get("/papers", { params: { project_id: pid } }).then((r) => setPapers(r.data)); }, [pid]);
  const toggle = (id) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : sel.length < 6 ? [...sel, id] : sel);
  const run = async () => {
    setBusy(true); setRes(null);
    try { setRes((await api.post("/compare", { project_id: pid, paper_ids: sel })).data); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); }
  };
  if (papers.length < 2) return <Empty testid="compare-empty" icon={Columns3} title="Add at least 2 papers to this project to compare them" />;
  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-card p-4">
        <div className="text-sm font-medium mb-2">Select 2–6 papers ({sel.length} selected)</div>
        <div className="space-y-1.5 max-h-64 overflow-y-auto" data-testid="compare-paper-list">
          {papers.map((p) => (
            <label key={p.id} className="flex items-start gap-2 text-sm cursor-pointer">
              <Checkbox checked={sel.includes(p.id)} onCheckedChange={() => toggle(p.id)} disabled={!sel.includes(p.id) && sel.length >= 6} data-testid={`compare-check-${p.id}`} className="mt-0.5" />
              <span>{p.title} <span className="text-xs text-muted-foreground">{p.year || ""} · {p.origin === "upload" ? "full text" : p.abstract ? "abstract" : "metadata"}</span></span>
            </label>
          ))}
        </div>
        <Button className="mt-3" onClick={run} disabled={busy || sel.length < 2} data-testid="compare-run-button">{busy && <Loader2 size={15} className="mr-1 animate-spin" />}Compare</Button>
      </div>
      {res && (
        <div className="rounded-lg border bg-card p-4" data-testid="compare-result">
          <div className="flex justify-between items-center mb-3">
            <div className="text-xs text-muted-foreground">Values come only from each paper's available content. "Not reported" = absent.</div>
            <Button size="sm" variant="outline" data-testid="compare-export-csv" onClick={() => downloadBlob(new Blob([toCSV(res)], { type: "text/csv" }), "paper_comparison.csv")}><Download size={14} className="mr-1" />Export CSV</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="text-sm border-collapse min-w-full" data-testid="compare-table">
              <thead><tr><th className="border p-2 bg-muted text-left w-32" />{res.rows.map((r) => (
                <th key={r.paper_id} className="border p-2 bg-muted text-left align-top min-w-[220px]">{r.title}<div className="text-xs font-normal text-muted-foreground">{r.year || "n.d."} · {r.basis}</div></th>
              ))}</tr></thead>
              <tbody>{res.fields.map((f) => (
                <tr key={f}><td className="border p-2 font-medium align-top">{LABELS[f]}</td>
                  {res.rows.map((r) => <td key={r.paper_id} className={`border p-2 align-top ${r[f] === "Not reported" ? "italic text-muted-foreground" : ""}`}>{r[f]}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
