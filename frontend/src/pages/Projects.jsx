import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { FolderPlus, FolderKanban, Trash2, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader, Empty } from "@/components/common";
import { ProjectDialog } from "@/components/ProjectDialog";
import { api, errMsg } from "@/lib/api";

export default function Projects() {
  const [items, setItems] = useState(null);
  const [params, setParams] = useSearchParams();
  const [dlg, setDlg] = useState(params.get("new") ? { mode: "new" } : null);
  const load = () => api.get("/projects").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);

  const save = async (body) => {
    try {
      if (dlg.mode === "new") await api.post("/projects", body);
      else await api.put(`/projects/${dlg.project.id}`, body);
      toast.success("Project saved");
      load();
    } catch (e) { toast.error(errMsg(e)); throw e; }
  };
  const remove = async (p) => {
    if (!window.confirm(`Delete project "${p.title}"? Its notes, chats and reports are deleted; papers stay in your library.`)) return;
    await api.delete(`/projects/${p.id}`);
    toast.success("Project deleted");
    load();
  };
  const close = (o) => { if (!o) { setDlg(null); setParams({}); } };

  return (
    <div>
      <PageHeader title="Projects" subtitle="Each project keeps its own papers, notes, chats and reports.">
        <Button data-testid="new-project-button" onClick={() => setDlg({ mode: "new" })}><FolderPlus size={16} className="mr-1.5" />New project</Button>
      </PageHeader>
      {items && items.length === 0 && <Empty testid="projects-empty" icon={FolderKanban} title="No projects yet" text="Create your first research project." />}
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="projects-list">
        {(items || []).map((p) => (
          <div key={p.id} className="rounded-lg border bg-card p-5 flex flex-col hover:border-primary/40 transition-colors fade-up" data-testid={`project-card-${p.id}`}>
            <Link to={`/projects/${p.id}`} className="font-display font-semibold text-lg hover:text-primary" data-testid="project-card-title">{p.title}</Link>
            <p className="text-sm text-muted-foreground mt-2 line-clamp-3 flex-1">{p.objectives || "No objectives set."}</p>
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs font-mono text-muted-foreground">{p.paper_count} papers</span>
              <div className="flex gap-1">
                <Button size="icon" variant="ghost" data-testid={`edit-project-${p.id}`} onClick={() => setDlg({ mode: "edit", project: p })}><Pencil size={15} /></Button>
                <Button size="icon" variant="ghost" data-testid={`delete-project-${p.id}`} onClick={() => remove(p)}><Trash2 size={15} /></Button>
              </div>
            </div>
          </div>
        ))}
      </div>
      {dlg && <ProjectDialog open onOpenChange={close} initial={dlg.project} onSave={save} />}
    </div>
  );
}
