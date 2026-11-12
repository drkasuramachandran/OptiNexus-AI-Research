import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { Pencil, BookOpen, Trash2, FileBarChart, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PageHeader, Empty, Md, Panel } from "@/components/common";
import { PaperCard } from "@/components/PaperCard";
import { ProjectDialog } from "@/components/ProjectDialog";
import NotesPanel from "@/components/NotesPanel";
import ChatWorkspace from "@/components/ChatWorkspace";
import ComparePanel from "@/components/ComparePanel";
import { api, errMsg } from "@/lib/api";

const ProjectPapers = ({ pid }) => {
  const [papers, setPapers] = useState([]);
  const load = () => api.get("/papers", { params: { project_id: pid } }).then((r) => setPapers(r.data));
  useEffect(() => { load(); }, [pid]); // eslint-disable-line
  const unlink = async (p) => {
    await api.patch(`/papers/${p.id}`, { project_ids: p.project_ids.filter((x) => x !== pid) });
    load();
  };
  if (!papers.length) return <Empty testid="project-papers-empty" icon={BookOpen} title="No papers in this project" text="Add papers from Literature Search, Library or upload PDFs in Paper Analyzer." />;
  return (
    <div className="space-y-3" data-testid="project-papers-list">
      {papers.map((p) => (
        <PaperCard key={p.id} p={p} testid={`project-paper-${p.id}`}
          actions={<Button size="sm" variant="ghost" onClick={() => unlink(p)} data-testid={`unlink-paper-${p.id}`}><X size={14} className="mr-1" />Remove from project</Button>} />
      ))}
    </div>
  );
};

const Reports = ({ pid }) => {
  const [items, setItems] = useState([]);
  const [view, setView] = useState(null);
  const load = () => api.get("/reports", { params: { project_id: pid } }).then((r) => setItems(r.data));
  useEffect(() => { load(); }, [pid]); // eslint-disable-line
  if (!items.length) return <Empty testid="reports-empty" icon={FileBarChart} title="No reports yet" text="In the Chat tab, use “Save as report” on any assistant answer." />;
  return (
    <div className="space-y-2" data-testid="reports-list">
      {items.map((r) => (
        <div key={r.id} className="flex items-center justify-between rounded-md border bg-card p-3">
          <button className="text-left" onClick={() => setView(r)} data-testid={`report-${r.id}`}>
            <div className="font-medium">{r.title}</div>
            <div className="text-xs text-muted-foreground font-mono">{new Date(r.created_at).toLocaleString()}</div>
          </button>
          <Button size="icon" variant="ghost" onClick={async () => { await api.delete(`/reports/${r.id}`); load(); }} data-testid={`delete-report-${r.id}`}><Trash2 size={15} /></Button>
        </div>
      ))}
      <Dialog open={!!view} onOpenChange={(o) => !o && setView(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{view?.title}</DialogTitle></DialogHeader>
          <Md>{view?.content}</Md>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default function ProjectDetail() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [err, setErr] = useState("");
  const [edit, setEdit] = useState(false);
  useEffect(() => { api.get(`/projects/${id}`).then((r) => setP(r.data)).catch((e) => setErr(errMsg(e))); }, [id]);
  if (err) return <Empty testid="project-not-found" title={err} ><Link to="/projects" className="text-primary">Back to projects</Link></Empty>;
  if (!p) return <div className="text-muted-foreground">Loading…</div>;
  const save = async (body) => {
    try { const r = await api.put(`/projects/${id}`, body); setP(r.data); toast.success("Project updated"); }
    catch (e) { toast.error(errMsg(e)); throw e; }
  };
  return (
    <div>
      <PageHeader title={p.title} subtitle="Project workspace">
        <Button variant="outline" onClick={() => setEdit(true)} data-testid="edit-project-button"><Pencil size={15} className="mr-1.5" />Edit</Button>
      </PageHeader>
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <Panel><div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Objectives</div><p className="text-sm whitespace-pre-wrap" data-testid="project-objectives">{p.objectives || "—"}</p></Panel>
        <Panel><div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Research questions</div><p className="text-sm whitespace-pre-wrap" data-testid="project-questions">{p.research_questions || "—"}</p></Panel>
      </div>
      <Tabs defaultValue="papers">
        <TabsList>
          <TabsTrigger value="papers" data-testid="tab-papers">Papers</TabsTrigger>
          <TabsTrigger value="notes" data-testid="tab-notes">Notes</TabsTrigger>
          <TabsTrigger value="chat" data-testid="tab-chat">Chat</TabsTrigger>
          <TabsTrigger value="reports" data-testid="tab-reports">Reports</TabsTrigger>
          <TabsTrigger value="compare" data-testid="tab-compare">Compare</TabsTrigger>
        </TabsList>
        <TabsContent value="papers" className="mt-5"><ProjectPapers pid={id} /></TabsContent>
        <TabsContent value="notes" className="mt-5"><NotesPanel projectId={id} /></TabsContent>
        <TabsContent value="chat" className="mt-5"><ChatWorkspace projectId={id} /></TabsContent>
        <TabsContent value="reports" className="mt-5"><Reports pid={id} /></TabsContent>
        <TabsContent value="compare" className="mt-5"><ComparePanel pid={id} /></TabsContent>
      </Tabs>
      {edit && <ProjectDialog open onOpenChange={setEdit} initial={p} onSave={save} />}
    </div>
  );
}
