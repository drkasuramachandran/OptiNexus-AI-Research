import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

export const ProjectDialog = ({ open, onOpenChange, initial, onSave }) => {
  const [f, setF] = useState(initial || { title: "", objectives: "", research_questions: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await onSave({ title: f.title, objectives: f.objectives, research_questions: f.research_questions }); onOpenChange(false); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="project-dialog">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader><DialogTitle>{initial ? "Edit project" : "New project"}</DialogTitle></DialogHeader>
          <div className="space-y-1.5"><Label>Title</Label><Input data-testid="project-title-input" value={f.title} onChange={set("title")} required /></div>
          <div className="space-y-1.5"><Label>Objectives</Label><Textarea data-testid="project-objectives-input" rows={3} value={f.objectives} onChange={set("objectives")} /></div>
          <div className="space-y-1.5"><Label>Research questions</Label><Textarea data-testid="project-questions-input" rows={3} value={f.research_questions} onChange={set("research_questions")} /></div>
          <DialogFooter><Button data-testid="project-save-button" disabled={busy}>{busy ? "Saving…" : "Save"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
