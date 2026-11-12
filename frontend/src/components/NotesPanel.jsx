import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, StickyNote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Empty } from "@/components/common";
import { api, errMsg } from "@/lib/api";

export default function NotesPanel({ projectId, projects }) {
  const [notes, setNotes] = useState([]);
  const [sel, setSel] = useState(null);
  const [filter, setFilter] = useState("all");
  const load = () => api.get("/notes", { params: projectId ? { project_id: projectId } : {} }).then((r) => setNotes(r.data));
  useEffect(() => { load(); }, [projectId]); // eslint-disable-line

  const create = async () => {
    const r = await api.post("/notes", { title: "Untitled note", content: "", project_id: projectId || null });
    setNotes([r.data, ...notes]);
    setSel(r.data);
  };
  const save = async () => {
    try {
      const r = await api.put(`/notes/${sel.id}`, { title: sel.title || "Untitled note", content: sel.content, project_id: sel.project_id || null });
      setNotes(notes.map((n) => (n.id === sel.id ? r.data : n)));
      toast.success("Note saved");
    } catch (e) { toast.error(errMsg(e)); }
  };
  const remove = async (n) => {
    await api.delete(`/notes/${n.id}`);
    setNotes(notes.filter((x) => x.id !== n.id));
    if (sel?.id === n.id) setSel(null);
  };
  const shown = filter === "all" ? notes : notes.filter((n) => (filter === "none" ? !n.project_id : n.project_id === filter));
  const pname = (id) => projects?.find((p) => p.id === id)?.title;

  return (
    <div className="grid md:grid-cols-[280px_1fr] gap-4 min-h-[420px]">
      <div className="space-y-2">
        <Button className="w-full" onClick={create} data-testid="new-note-button"><Plus size={15} className="mr-1" />New note</Button>
        {projects && (
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger data-testid="notes-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All notes</SelectItem>
              <SelectItem value="none">General (no project)</SelectItem>
              {projects.map((p) => <SelectItem key={p.id} value={p.id}>{p.title}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        <div className="space-y-1" data-testid="notes-list">
          {shown.map((n) => (
            <div key={n.id} className={`group flex items-center justify-between rounded-md border px-3 py-2 cursor-pointer ${sel?.id === n.id ? "border-primary bg-primary/10" : "bg-card hover:border-primary/40"}`} onClick={() => setSel(n)} data-testid={`note-item-${n.id}`}>
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{n.title}</div>
                {projects && <div className="text-[11px] text-muted-foreground truncate">{pname(n.project_id) || "General"}</div>}
              </div>
              <button onClick={(e) => { e.stopPropagation(); remove(n); }} className="opacity-60 hover:opacity-100" data-testid={`delete-note-${n.id}`}><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      </div>
      {sel ? (
        <div className="rounded-lg border bg-card p-4 space-y-3">
          <Input data-testid="note-title-input" value={sel.title} onChange={(e) => setSel({ ...sel, title: e.target.value })} className="font-semibold" />
          {projects && (
            <Select value={sel.project_id || "none"} onValueChange={(v) => setSel({ ...sel, project_id: v === "none" ? null : v })}>
              <SelectTrigger data-testid="note-project-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No project</SelectItem>
                {projects.map((p) => <SelectItem key={p.id} value={p.id}>{p.title}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
          <Textarea data-testid="note-content-input" rows={14} value={sel.content} onChange={(e) => setSel({ ...sel, content: e.target.value })} placeholder="Write your note…" />
          <Button onClick={save} data-testid="save-note-button">Save note</Button>
        </div>
      ) : <Empty icon={StickyNote} title="Select or create a note" />}
    </div>
  );
}
