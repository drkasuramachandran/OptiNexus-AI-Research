import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Download, FileDown, PenLine, AlertTriangle, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { PageHeader, Panel, Empty, Md } from "@/components/common";
import { downloadBlob } from "@/components/ComparePanel";
import { api, errMsg } from "@/lib/api";

const TYPES = [["proposal", "Research proposal"], ["literature_review", "Literature review"], ["abstract", "Abstract"], ["manuscript_section", "Manuscript section"]];
const STYLES = ["APA", "IEEE", "Vancouver", "Harvard"];

const Pick = ({ value, onChange, items, testid }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger data-testid={testid}><SelectValue placeholder="Select…" /></SelectTrigger>
    <SelectContent>{items.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
  </Select>
);

export default function WritingStudio() {
  const [projects, setProjects] = useState([]);
  const [pid, setPid] = useState("");
  const [papers, setPapers] = useState([]);
  const [sel, setSel] = useState([]);
  const [f, setF] = useState({ doc_type: "literature_review", style: "APA", instructions: "" });
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState(null);
  const [preview, setPreview] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [draftId, setDraftId] = useState(null);
  const [draftTitle, setDraftTitle] = useState("");
  useEffect(() => { api.get("/projects").then((r) => setProjects(r.data)); }, []);
  const loadDrafts = () => api.get("/drafts", { params: { project_id: pid } }).then((r) => setDrafts(r.data));
  useEffect(() => { if (pid) { loadDrafts(); setDraft(null); setDraftId(null); } }, [pid]); // eslint-disable-line
  useEffect(() => { if (pid) api.get("/papers", { params: { project_id: pid } }).then((r) => { setPapers(r.data); setSel(r.data.map((p) => p.id)); }); }, [pid]);

  const generate = async () => {
    setBusy(true);
    try { setDraft((await api.post("/writing/draft", { project_id: pid, paper_ids: sel, ...f })).data); setPreview(false); setDraftId(null); setDraftTitle(""); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); }
  };
  const saveDraft = async () => {
    const body = { project_id: pid, title: draftTitle.trim() || title, markdown: draft.markdown, doc_type: f.doc_type, style: f.style, paper_ids: sel };
    try {
      const r = draftId ? await api.put(`/drafts/${draftId}`, body) : await api.post("/drafts", body);
      setDraftId(r.data.id); setDraftTitle(r.data.title); loadDrafts();
      toast.success("Draft saved to project");
    } catch (e) { toast.error(errMsg(e)); }
  };
  const openDraft = (d) => {
    setDraft({ markdown: d.markdown }); setDraftId(d.id); setDraftTitle(d.title); setPreview(false);
    setF({ ...f, doc_type: d.doc_type || f.doc_type, style: d.style || f.style });
    if (d.paper_ids?.length) setSel(d.paper_ids);
  };
  const removeDraft = async (d) => {
    if (!window.confirm(`Delete draft "${d.title}"?`)) return;
    await api.delete(`/drafts/${d.id}`);
    if (draftId === d.id) { setDraft(null); setDraftId(null); }
    loadDrafts();
  };
  const title = draftTitle.trim() || `${TYPES.find((t) => t[0] === f.doc_type)[1]} draft`;
  const docx = async () => {
    try { const r = await api.post("/writing/docx", { title, markdown: draft.markdown }, { responseType: "blob" }); downloadBlob(r.data, `${title.replace(/\s+/g, "_")}.docx`); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const unsupported = draft ? (draft.markdown.match(/\[UNSUPPORTED/g) || []).length : 0;

  return (
    <div>
      <PageHeader title="Writing Studio" subtitle="Drafts cite only papers in your project. Claims without support are flagged inline as [UNSUPPORTED]." />
      <div className="grid lg:grid-cols-[340px_1fr] gap-6">
        <Panel className="space-y-3 h-fit">
          <Pick value={pid} onChange={setPid} items={projects.map((p) => [p.id, p.title])} testid="writing-project-select" />
          <Pick value={f.doc_type} onChange={(v) => setF({ ...f, doc_type: v })} items={TYPES} testid="writing-type-select" />
          <Pick value={f.style} onChange={(v) => setF({ ...f, style: v })} items={STYLES.map((s) => [s, s])} testid="writing-style-select" />
          <Textarea data-testid="writing-instructions" rows={3} placeholder="Instructions (e.g. focus on temperature compensation; section: Introduction)" value={f.instructions} onChange={(e) => setF({ ...f, instructions: e.target.value })} />
          {pid && (
            <div>
              <div className="text-sm font-medium mb-1.5">Source papers ({sel.length})</div>
              {papers.length === 0 ? <div className="text-xs text-muted-foreground">This project has no papers.</div> : (
                <div className="space-y-1.5 max-h-56 overflow-y-auto" data-testid="writing-paper-list">
                  {papers.map((p) => (
                    <label key={p.id} className="flex items-start gap-2 text-xs cursor-pointer">
                      <Checkbox className="mt-0.5" checked={sel.includes(p.id)} data-testid={`writing-check-${p.id}`} onCheckedChange={() => setSel(sel.includes(p.id) ? sel.filter((x) => x !== p.id) : [...sel, p.id])} />
                      <span>{p.title}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
          <Button className="w-full" onClick={generate} disabled={busy || !pid || !sel.length} data-testid="writing-generate-button">
            {busy ? <Loader2 size={15} className="mr-1 animate-spin" /> : <PenLine size={15} className="mr-1" />}{busy ? "Drafting (up to a minute)…" : "Generate draft"}
          </Button>
          {pid && (
            <div className="pt-2 border-t">
              <div className="text-sm font-medium mb-1.5">Saved drafts ({drafts.length})</div>
              {drafts.length === 0 ? <div className="text-xs text-muted-foreground">No saved drafts in this project.</div> : (
                <div className="space-y-1" data-testid="saved-drafts-list">
                  {drafts.map((d) => (
                    <div key={d.id} className={`flex items-center justify-between rounded-md border px-2.5 py-1.5 text-xs cursor-pointer ${draftId === d.id ? "border-primary bg-primary/10" : "hover:border-primary/40"}`} onClick={() => openDraft(d)} data-testid={`saved-draft-${d.id}`}>
                      <div className="min-w-0"><div className="truncate font-medium">{d.title}</div><div className="text-muted-foreground">{new Date(d.updated_at).toLocaleString()}</div></div>
                      <button onClick={(e) => { e.stopPropagation(); removeDraft(d); }} data-testid={`delete-draft-${d.id}`}><Trash2 size={13} /></button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Panel>
        {!draft ? <Empty icon={PenLine} title="No draft yet" text="Choose a project, document type, citation style and source papers." /> : (
          <Panel className="space-y-3" data-testid="writing-draft">
            <div className="flex gap-2">
              <Input data-testid="draft-title-input" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} placeholder={title} />
              <Button size="sm" onClick={saveDraft} data-testid="save-draft-button"><Save size={14} className="mr-1" />{draftId ? "Save changes" : "Save draft"}</Button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className={`text-xs flex items-center gap-1 ${unsupported ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}`} data-testid="unsupported-count">
                <AlertTriangle size={13} />{unsupported} unsupported claim flag(s){draft.cited ? ` · ${draft.cited.length} of ${draft.cited.length + draft.uncited.length} papers cited` : ""}
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => setPreview(!preview)} data-testid="writing-preview-toggle">{preview ? "Edit" : "Preview"}</Button>
                <Button size="sm" variant="outline" onClick={() => downloadBlob(new Blob([draft.markdown], { type: "text/markdown" }), `${title.replace(/\s+/g, "_")}.md`)} data-testid="export-md-button"><Download size={14} className="mr-1" />Markdown</Button>
                <Button size="sm" variant="outline" onClick={docx} data-testid="export-docx-button"><FileDown size={14} className="mr-1" />DOCX</Button>
              </div>
            </div>
            {preview ? <div className="rounded-md border p-4"><Md>{draft.markdown.replace(/\[UNSUPPORTED([^\]]*)\]/g, "**`[UNSUPPORTED$1]`**")}</Md></div> : (
              <Textarea data-testid="writing-editor" className="font-mono text-sm min-h-[520px]" value={draft.markdown} onChange={(e) => setDraft({ ...draft, markdown: e.target.value })} />
            )}
          </Panel>
        )}
      </div>
    </div>
  );
}
