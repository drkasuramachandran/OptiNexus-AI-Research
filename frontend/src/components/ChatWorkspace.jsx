import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Send, Loader2, Bot, User, FileBarChart, MessagesSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Md, Empty } from "@/components/common";
import { GapCards } from "@/components/GapCards";
import { api, errMsg, streamSSE } from "@/lib/api";

const MODES = [["auto", "Auto (orchestrator picks)"], ["literature_review", "Literature Review"], ["gap_discovery", "Research Gap Discovery"],
  ["paper_comparison", "Paper Comparison"], ["scientific_writing", "Scientific Writing"], ["experimental_planning", "Experimental Planning"]];

const Message = ({ m, onReport }) => (
  <div className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`} data-testid={`chat-message-${m.role}`}>
    {m.role !== "user" && <div className="h-7 w-7 rounded-full bg-primary/15 text-primary grid place-items-center shrink-0"><Bot size={15} /></div>}
    <div className={`rounded-lg px-4 py-3 max-w-[85%] ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-card border"}`}>
      {m.mode_label && <div className="text-[10px] font-mono uppercase tracking-wider text-primary mb-1" data-testid="message-mode">{m.mode_label} · {m.papers_in_context} papers in context</div>}
      {m.role === "user" ? <p className="text-sm whitespace-pre-wrap">{m.content}</p> : <Md>{m.content}</Md>}
      {m.gaps && <GapCards gaps={m.gaps} />}
      {m.role === "assistant" && onReport && m.content && (
        <Button size="sm" variant="ghost" className="mt-1 h-7 px-2 text-xs" onClick={() => onReport(m)} data-testid="save-report-button"><FileBarChart size={13} className="mr-1" />Save as report</Button>
      )}
    </div>
    {m.role === "user" && <div className="h-7 w-7 rounded-full bg-secondary grid place-items-center shrink-0"><User size={15} /></div>}
  </div>
);

export default function ChatWorkspace({ projectId, projects }) {
  const [convs, setConvs] = useState([]);
  const [conv, setConv] = useState(null);
  const [mode, setMode] = useState("auto");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [newProject, setNewProject] = useState("none");
  const endRef = useRef();
  const loadList = () => api.get("/conversations", { params: projectId ? { project_id: projectId } : {} }).then((r) => setConvs(r.data));
  useEffect(() => { loadList(); }, [projectId]); // eslint-disable-line
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [conv?.messages?.length, conv?.messages?.at?.(-1)?.content]);

  const open = async (id) => setConv((await api.get(`/conversations/${id}`)).data);
  const create = async () => {
    const pid = projectId || (newProject === "none" ? null : newProject);
    const r = await api.post("/conversations", { project_id: pid });
    setConvs([r.data, ...convs]);
    setConv(r.data);
    return r.data;
  };
  const remove = async (c) => {
    await api.delete(`/conversations/${c.id}`);
    setConvs(convs.filter((x) => x.id !== c.id));
    if (conv?.id === c.id) setConv(null);
  };
  const send = async () => {
    if (!text.trim()) return;
    const c = conv || (await create());
    const content = text;
    setText("");
    setBusy(true);
    const draft = { role: "assistant", content: "" };
    let msgs = [...(c.messages || []), { role: "user", content }, draft];
    setConv({ ...c, title: c.messages?.length ? c.title : content.slice(0, 60), messages: msgs });
    try {
      await streamSSE(`/conversations/${c.id}/messages`, { content, mode }, (ev) => {
        if (ev.type === "meta") Object.assign(draft, { mode_label: ev.mode_label + (ev.auto ? " (auto)" : ""), papers_in_context: ev.papers_in_context });
        else if (ev.type === "delta") draft.content += ev.text;
        else if (ev.type === "error") { draft.content = `**Error:** ${ev.error}`; toast.error(ev.error); }
        else if (ev.type === "done") Object.assign(draft, ev.message, { mode_label: draft.mode_label });
        msgs = [...msgs.slice(0, -1), { ...draft }];
        setConv((cur) => ({ ...cur, messages: msgs }));
      });
      loadList();
    } catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };
  const runGaps = async () => {
    const c = conv || (await create());
    setBusy(true);
    try {
      const r = await api.post(`/conversations/${c.id}/gaps`);
      setConv((cur) => ({ ...cur, title: cur.messages?.length ? cur.title : "Structured gap analysis", messages: [...(cur.messages || []), ...r.data.messages] }));
      loadList();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); }
  };
  const report = async (m) => {
    try {
      await api.post("/reports", { project_id: conv.project_id, title: `${m.mode_label || "Assistant"} — ${conv.title}`.slice(0, 120), content: m.content });
      toast.success("Saved to project reports");
    } catch (e) { toast.error(errMsg(e)); }
  };
  const pname = (id) => projects?.find((p) => p.id === id)?.title;

  return (
    <div className="grid md:grid-cols-[260px_1fr] gap-4 h-[calc(100vh-220px)] min-h-[520px]">
      <div className="flex flex-col gap-2 min-h-0">
        {!projectId && projects && (
          <Select value={newProject} onValueChange={setNewProject}>
            <SelectTrigger data-testid="new-chat-project-select"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="none">Context: whole library</SelectItem>{projects.map((p) => <SelectItem key={p.id} value={p.id}>Context: {p.title}</SelectItem>)}</SelectContent>
          </Select>
        )}
        <Button onClick={create} data-testid="new-conversation-button"><Plus size={15} className="mr-1" />New conversation</Button>
        <div className="flex-1 overflow-y-auto space-y-1" data-testid="conversation-list">
          {convs.map((c) => (
            <div key={c.id} onClick={() => open(c.id)} data-testid={`conversation-${c.id}`}
              className={`group flex items-center justify-between rounded-md border px-3 py-2 cursor-pointer ${conv?.id === c.id ? "border-primary bg-primary/10" : "bg-card hover:border-primary/40"}`}>
              <div className="min-w-0"><div className="text-sm truncate">{c.title}</div>
                {!projectId && <div className="text-[11px] text-muted-foreground truncate">{pname(c.project_id) || "Whole library"}</div>}</div>
              <button onClick={(e) => { e.stopPropagation(); remove(c); }} className="opacity-60 hover:opacity-100"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-col rounded-lg border bg-background min-h-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4" data-testid="chat-messages">
          {!conv?.messages?.length ? (
            <Empty icon={MessagesSquare} title="Ask the research assistant" text="Answers use only your saved papers and uploaded PDFs as evidence, with labelled statements. Choose a mode or let the orchestrator decide." />
          ) : conv.messages.map((m, i) => <Message key={m.id || i} m={m} onReport={conv.project_id ? report : null} />)}
          {busy && !conv?.messages?.at(-1)?.content && <div className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Thinking…</div>}
          <div ref={endRef} />
        </div>
        <div className="border-t p-3 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
          <Select value={mode} onValueChange={setMode}>
            <SelectTrigger className="w-64" data-testid="chat-mode-select"><SelectValue /></SelectTrigger>
            <SelectContent>{MODES.map(([v, l]) => <SelectItem key={v} value={v} data-testid={`mode-option-${v}`}>{l}</SelectItem>)}</SelectContent>
          </Select>
          {mode === "gap_discovery" && (
            <Button size="sm" variant="outline" onClick={runGaps} disabled={busy} data-testid="run-structured-gaps-button">Run structured gap analysis</Button>
          )}
          </div>
          <div className="flex gap-2">
            <Textarea data-testid="chat-input" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about your papers…"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <Button onClick={send} disabled={busy || !text.trim()} data-testid="chat-send-button" className="self-end">{busy ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />}</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
