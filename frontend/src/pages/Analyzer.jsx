import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, FileText, Loader2, AlertTriangle, RefreshCw, MessageSquareQuote, Quote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { PageHeader, Panel, Empty } from "@/components/common";
import { api, errMsg } from "@/lib/api";

const FIELDS = [["title", "Title"], ["authors", "Authors"], ["year", "Year"], ["journal", "Journal"], ["doi", "DOI"], ["problem", "Problem"],
  ["objectives", "Objectives"], ["methods", "Methods"], ["experimental_setup", "Experimental setup"], ["instruments", "Instruments"],
  ["parameters", "Parameters"], ["results", "Results"], ["limitations", "Limitations"], ["conclusions", "Conclusions"], ["future_work", "Future work"]];

const Profile = ({ p, onReanalyze }) => {
  if (p.status === "processing") return <Panel className="flex items-center gap-2 text-muted-foreground"><Loader2 className="animate-spin" size={16} />Generating structured profile…</Panel>;
  if (p.status === "profile_failed") return (
    <Panel className="text-sm"><div className="flex items-center gap-2 text-destructive"><AlertTriangle size={16} />{p.error}</div>
      <Button size="sm" className="mt-3" variant="outline" onClick={onReanalyze} data-testid="reanalyze-button"><RefreshCw size={14} className="mr-1" />Retry analysis</Button></Panel>
  );
  return (
    <Panel data-testid="paper-profile">
      <div className="text-xs text-muted-foreground font-mono mb-3">{p.filename} · {p.page_count} pages · {p.chunk_count} chunks</div>
      <dl className="grid sm:grid-cols-[160px_1fr] gap-x-4 gap-y-2.5 text-sm">
        {FIELDS.map(([k, label]) => {
          const v = p.profile?.[k];
          const nf = !v || v === "Not found in document";
          return [<dt key={k + "l"} className="text-muted-foreground">{label}</dt>,
            <dd key={k} data-testid={`profile-${k}`} className={nf ? "italic text-muted-foreground/70" : ""}>{v || "Not found in document"}</dd>];
        })}
      </dl>
    </Panel>
  );
};

const QA = ({ paper, projects }) => {
  const [scope, setScope] = useState("paper");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState(null);
  const ask = async () => {
    setBusy(true); setAns(null);
    try {
      const body = scope === "paper" ? { question: q, paper_id: paper?.id } : { question: q, project_id: scope };
      setAns((await api.post("/qa", body)).data);
    } catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); }
  };
  return (
    <Panel>
      <h3 className="font-semibold flex items-center gap-2 mb-3"><MessageSquareQuote size={17} className="text-primary" />Ask the documents</h3>
      <Select value={scope} onValueChange={setScope}>
        <SelectTrigger data-testid="qa-scope-select" className="mb-2"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="paper" disabled={!paper}>This paper{paper ? `: ${paper.filename}` : ""}</SelectItem>
          {projects.map((p) => <SelectItem key={p.id} value={p.id}>All PDFs in project: {p.title}</SelectItem>)}
        </SelectContent>
      </Select>
      <Textarea data-testid="qa-question-input" rows={3} value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. What wavelength and sensitivity were reported?" />
      <Button className="mt-2" onClick={ask} disabled={busy || q.length < 3 || (scope === "paper" && !paper)} data-testid="qa-ask-button">
        {busy ? <Loader2 className="animate-spin mr-1" size={15} /> : null}Ask
      </Button>
      {ans && (
        <div className="mt-4 space-y-3" data-testid="qa-answer">
          <p className={`text-sm whitespace-pre-wrap ${ans.evidence_found ? "" : "text-amber-600 dark:text-amber-400"}`} data-testid="qa-answer-text">{ans.answer}</p>
          <div className="text-xs text-muted-foreground">Searched {ans.documents_searched} document(s).</div>
          {ans.citations.map((c, i) => (
            <div key={i} className="rounded-md border-l-2 border-primary bg-muted/50 p-3 text-sm" data-testid={`qa-citation-${i}`}>
              <div className="text-xs font-mono text-primary mb-1">[{c.source}] {c.document} · page {c.page} · {c.section}</div>
              <div className="flex gap-2"><Quote size={13} className="shrink-0 mt-1 text-muted-foreground" /><span className="italic">{c.excerpt}</span></div>
              {!c.verbatim && <div className="text-[11px] text-muted-foreground mt-1">Excerpt shown from retrieved passage (model quote could not be matched verbatim).</div>}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
};

export default function Analyzer() {
  const [papers, setPapers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState("none");
  const [sel, setSel] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();
  const load = () => api.get("/papers", { params: { origin: "upload" } }).then((r) => setPapers(r.data));
  useEffect(() => { load(); api.get("/projects").then((r) => setProjects(r.data)); }, []);
  const processing = papers.some((p) => p.status === "processing");
  useEffect(() => { if (!processing) return; const t = setInterval(load, 3000); return () => clearInterval(t); }, [processing]);
  const selected = papers.find((p) => p.id === sel);

  const upload = async (files) => {
    const list = [...files];
    const bad = list.filter((f) => !f.name.toLowerCase().endsWith(".pdf") || f.size > 20 * 1024 * 1024);
    bad.forEach((f) => toast.error(`${f.name}: must be a PDF under 20 MB`));
    const ok = list.filter((f) => !bad.includes(f));
    if (!ok.length) return;
    const fd = new FormData();
    ok.forEach((f) => fd.append("files", f));
    fd.append("project_id", project === "none" ? "" : project);
    setBusy(true);
    try {
      const r = await api.post("/papers/upload", fd);
      r.data.results.forEach((x) => (x.ok ? toast.success(`${x.filename}: ${x.pages} pages extracted`) : toast.error(`${x.filename}: ${x.error}`)));
      await load();
      const first = r.data.results.find((x) => x.ok);
      if (first) setSel(first.paper_id);
    } catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); fileRef.current.value = ""; }
  };
  const reanalyze = async () => { await api.post(`/papers/${sel}/reanalyze`); load(); };

  return (
    <div>
      <PageHeader title="Paper Analyzer" subtitle="Upload text-based PDFs (max 20 MB each). Original files are not stored — only extracted text with page and section metadata." />
      <div className="grid lg:grid-cols-[320px_1fr] gap-6">
        <div className="space-y-4">
          <Panel>
            <Select value={project} onValueChange={setProject}>
              <SelectTrigger data-testid="upload-project-select" className="mb-3"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="none">No project</SelectItem>{projects.map((p) => <SelectItem key={p.id} value={p.id}>Add to: {p.title}</SelectItem>)}</SelectContent>
            </Select>
            <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-lg p-6 cursor-pointer hover:border-primary/60 transition-colors text-center"
              onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files); }}>
              {busy ? <Loader2 className="animate-spin text-primary" /> : <Upload className="text-primary" />}
              <span className="text-sm">{busy ? "Extracting text…" : "Drop PDFs or click to upload"}</span>
              <input ref={fileRef} data-testid="pdf-upload-input" type="file" accept="application/pdf,.pdf" multiple className="hidden" onChange={(e) => upload(e.target.files)} />
            </label>
          </Panel>
          <div className="space-y-1.5" data-testid="uploaded-list">
            {papers.length === 0 && <div className="text-sm text-muted-foreground">No PDFs uploaded yet.</div>}
            {papers.map((p) => (
              <button key={p.id} onClick={() => setSel(p.id)} data-testid={`uploaded-paper-${p.id}`}
                className={`w-full text-left rounded-md border px-3 py-2.5 flex items-start gap-2 ${sel === p.id ? "border-primary bg-primary/10" : "bg-card hover:border-primary/40"}`}>
                <FileText size={16} className="mt-0.5 shrink-0 text-primary" />
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{p.filename}</div>
                  <div className="text-[11px] text-muted-foreground">{p.status === "processing" ? "Analyzing…" : p.status === "profile_failed" ? "Profile failed" : `${p.page_count} pages · ready`}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-6">
          {selected ? <Profile p={selected} onReanalyze={reanalyze} /> : <Empty icon={FileText} title="Select an uploaded paper" text="Its structured profile will appear here." />}
          <QA paper={selected} projects={projects} />
        </div>
      </div>
    </div>
  );
}
