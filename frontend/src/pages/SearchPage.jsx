import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Search, BookmarkPlus, Check, Copy, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader, Panel, Empty, SourceBadge } from "@/components/common";
import { PaperCard } from "@/components/PaperCard";
import { ProjectPicker } from "@/components/ProjectPicker";
import { api, errMsg, citation } from "@/lib/api";

const NAMES = { openalex: "OpenAlex", crossref: "Crossref", arxiv: "arXiv", pubmed: "PubMed" };
const keyOf = (p) => p.doi || `${p.title}-${p.year}`;

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [f, setF] = useState({ year_from: "", year_to: "", author: "", journal: "" });
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState({});
  const [projects, setProjects] = useState([]);
  useEffect(() => { api.get("/projects").then((r) => setProjects(r.data)); }, []);

  const run = async (e) => {
    e.preventDefault();
    setBusy(true); setError(""); setRes(null);
    try {
      const body = { query: q, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v !== "").map(([k, v]) => [k, k.startsWith("year") ? Number(v) : v])) };
      const r = await api.post("/search", body);
      setRes(r.data);
    } catch (e2) { setError(errMsg(e2)); }
    finally { setBusy(false); }
  };

  const save = async (p, project_id) => {
    try {
      const r = await api.post("/papers", { ...p, project_id: project_id || null });
      setSaved({ ...saved, [keyOf(p)]: true });
      toast.success(project_id ? "Added to project" : r.data.already_saved ? "Already in your library" : "Saved to library");
    } catch (e) { toast.error(errMsg(e)); }
  };
  const copy = (p) => { navigator.clipboard.writeText(citation(p)); toast.success("Citation copied"); };
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  return (
    <div>
      <PageHeader title="Literature Search" subtitle='OpenAlex, Crossref, arXiv and PubMed queried in parallel. Supports AND, OR, NOT and "quoted phrases".' />
      <Panel className="mb-6">
        <form onSubmit={run} className="space-y-3">
          <div className="flex gap-2">
            <Input data-testid="search-query-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder='e.g. "fibre optic" AND interferometric NOT review' className="font-mono text-sm" required minLength={2} />
            <Button data-testid="search-submit-button" disabled={busy}>{busy ? <Loader2 className="animate-spin" size={16} /> : <Search size={16} />}<span className="ml-1.5">Search</span></Button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <Input data-testid="filter-year-from" type="number" placeholder="Year from" value={f.year_from} onChange={set("year_from")} />
            <Input data-testid="filter-year-to" type="number" placeholder="Year to" value={f.year_to} onChange={set("year_to")} />
            <Input data-testid="filter-author" placeholder="Author" value={f.author} onChange={set("author")} />
            <Input data-testid="filter-journal" placeholder="Journal" value={f.journal} onChange={set("journal")} />
          </div>
        </form>
      </Panel>
      {error && <div data-testid="search-error" className="mb-4 text-sm text-destructive">{error}</div>}
      {busy && <div className="text-muted-foreground text-sm flex items-center gap-2"><Loader2 className="animate-spin" size={16} />Querying sources (up to 15 s each)…</div>}
      {res && (
        <>
          <div className="flex flex-wrap gap-2 mb-5" data-testid="source-status">
            {Object.entries(res.sources).map(([k, s]) => (
              <div key={k} data-testid={`source-status-${k}`} className={`flex items-center gap-2 text-xs rounded-md border px-2.5 py-1.5 ${s.ok ? "" : "border-destructive/50 text-destructive"}`}>
                {s.ok ? <CheckCircle2 size={13} className="text-emerald-500" /> : <AlertTriangle size={13} />}
                <SourceBadge s={NAMES[k]} />
                {s.ok ? `${s.count} results` : `failed: ${s.error}`}
              </div>
            ))}
            {res.disabled.map((k) => <div key={k} className="text-xs rounded-md border px-2.5 py-1.5 text-muted-foreground">{NAMES[k]} disabled in Settings</div>)}
            <div className="text-xs text-muted-foreground px-2 py-1.5" data-testid="results-count">{res.raw_count} raw → {res.results.length} after merge & deduplication</div>
          </div>
          {res.results.length === 0 ? <Empty testid="search-empty" icon={Search} title="No results" text="Try broader terms or fewer filters." /> : (
            <div className="space-y-3" data-testid="search-results">
              {res.results.map((p, i) => (
                <PaperCard key={keyOf(p) + i} p={p} testid={`search-result-${i}`} actions={<>
                  <Button size="sm" data-testid={`save-result-${i}`} onClick={() => save(p)} variant={saved[keyOf(p)] ? "secondary" : "default"}>
                    {saved[keyOf(p)] ? <Check size={14} className="mr-1" /> : <BookmarkPlus size={14} className="mr-1" />}{saved[keyOf(p)] ? "Saved" : "Save to library"}
                  </Button>
                  <ProjectPicker projects={projects} onPick={(pid) => save(p, pid)} testid={`add-to-project-${i}`} />
                  <Button size="sm" variant="ghost" onClick={() => copy(p)} data-testid={`copy-citation-${i}`}><Copy size={14} className="mr-1" />Copy citation</Button>
                </>} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
