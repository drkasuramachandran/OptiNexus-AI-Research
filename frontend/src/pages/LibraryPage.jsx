import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Library, Trash2, Quote, Tag, X } from "lucide-react";
import { CitationDialog } from "@/components/CitationDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { PageHeader, Empty } from "@/components/common";
import { PaperCard } from "@/components/PaperCard";
import { ProjectPicker } from "@/components/ProjectPicker";
import { api, errMsg } from "@/lib/api";

const TagEditor = ({ p, onChange }) => {
  const [t, setT] = useState("");
  const add = (e) => { e.preventDefault(); if (t.trim()) onChange([...(p.tags || []), t.trim()]); setT(""); };
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-3">
      <Tag size={13} className="text-muted-foreground" />
      {(p.tags || []).map((x) => (
        <span key={x} className="text-xs rounded bg-secondary px-2 py-0.5 flex items-center gap-1">{x}
          <button onClick={() => onChange(p.tags.filter((y) => y !== x))}><X size={11} /></button></span>
      ))}
      <form onSubmit={add}><Input data-testid={`tag-input-${p.id}`} value={t} onChange={(e) => setT(e.target.value)} placeholder="add tag" className="h-7 w-28 text-xs" /></form>
    </div>
  );
};

export default function LibraryPage() {
  const [papers, setPapers] = useState(null);
  const [projects, setProjects] = useState([]);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("all");
  const [proj, setProj] = useState("all");
  const [cite, setCite] = useState(null);
  const load = () => api.get("/papers", { params: { q, tag: tag === "all" ? "" : tag, project_id: proj === "all" ? "" : proj } }).then((r) => setPapers(r.data));
  useEffect(() => { api.get("/projects").then((r) => setProjects(r.data)); }, []);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [q, tag, proj]); // eslint-disable-line

  const patch = async (p, body) => {
    try { const r = await api.patch(`/papers/${p.id}`, body); setPapers(papers.map((x) => (x.id === p.id ? r.data : x))); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const toggleProject = (p, pid) => patch(p, { project_ids: p.project_ids.includes(pid) ? p.project_ids.filter((x) => x !== pid) : [...p.project_ids, pid] });
  const remove = async (p) => {
    if (!window.confirm("Remove this paper from your library?")) return;
    await api.delete(`/papers/${p.id}`);
    setPapers(papers.filter((x) => x.id !== p.id));
  };
  const allTags = [...new Set((papers || []).flatMap((p) => p.tags || []))];
  const pname = (id) => projects.find((p) => p.id === id)?.title;

  return (
    <div>
      <PageHeader title="Library" subtitle="Saved search results and uploaded PDFs." />
      <div className="flex flex-wrap gap-2 mb-5">
        <Input data-testid="library-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, author, journal, DOI, tag…" className="max-w-sm" />
        <Select value={tag} onValueChange={setTag}>
          <SelectTrigger className="w-40" data-testid="library-tag-filter"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All tags</SelectItem>{allTags.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={proj} onValueChange={setProj}>
          <SelectTrigger className="w-48" data-testid="library-project-filter"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All projects</SelectItem>{projects.map((p) => <SelectItem key={p.id} value={p.id}>{p.title}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {papers && papers.length === 0 && <Empty testid="library-empty" icon={Library} title="Your library is empty" text="Save papers from Literature Search or upload PDFs in Paper Analyzer." />}
      <div className="space-y-3" data-testid="library-list">
        {(papers || []).map((p) => (
          <PaperCard key={p.id} p={p} testid={`library-paper-${p.id}`}
            actions={<>
              <ProjectPicker projects={projects} selected={p.project_ids} onPick={(pid) => toggleProject(p, pid)} label="Projects" testid={`library-projects-${p.id}`} />
              <Button size="sm" variant="ghost" onClick={() => setCite(p)} data-testid={`cite-paper-${p.id}`}><Quote size={14} className="mr-1" />Cite & verify</Button>
              <Button size="sm" variant="ghost" onClick={() => remove(p)} data-testid={`delete-paper-${p.id}`}><Trash2 size={14} className="mr-1" />Remove</Button>
            </>}
            footer={<>
              {p.project_ids?.length > 0 && <div className="text-xs text-muted-foreground mt-3">In: {p.project_ids.map(pname).filter(Boolean).join(", ")}</div>}
              <TagEditor p={p} onChange={(tags) => patch(p, { tags })} />
            </>} />
        ))}
      </div>
      {cite && <CitationDialog paper={cite} onClose={() => setCite(null)} />}
    </div>
  );
}
