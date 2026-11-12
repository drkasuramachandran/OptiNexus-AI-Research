import { useState } from "react";
import { ExternalLink, Unlock, Lock, HelpCircle } from "lucide-react";
import { SourceBadge } from "@/components/common";

const OA = ({ p }) => {
  if (p.origin === "upload") return <span className="text-xs text-primary flex items-center gap-1"><Unlock size={12} />Full text uploaded</span>;
  if (p.oa_available === true)
    return <a href={p.oa_url || p.url} target="_blank" rel="noreferrer" data-testid="oa-link" className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1"><Unlock size={12} />Open-access full text</a>;
  if (p.oa_available === false) return <span className="text-xs text-muted-foreground flex items-center gap-1"><Lock size={12} />Not open access</span>;
  return <span className="text-xs text-muted-foreground flex items-center gap-1"><HelpCircle size={12} />OA status not reported</span>;
};

export const PaperCard = ({ p, actions, footer, testid }) => {
  const [more, setMore] = useState(false);
  const authors = p.authors || [];
  return (
    <div data-testid={testid} className="rounded-lg border bg-card p-5 hover:border-primary/40 transition-colors fade-up">
      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        {(p.sources || []).map((s) => <SourceBadge key={s} s={s} />)}
        {p.year && <span className="text-xs font-mono text-muted-foreground ml-1">{p.year}</span>}
      </div>
      <h3 className="font-semibold leading-snug text-[15px]" data-testid="paper-title">{p.title}</h3>
      <div className="text-sm text-muted-foreground mt-1">
        {authors.length ? (authors.length > 6 ? `${authors.slice(0, 6).join(", ")} et al.` : authors.join(", ")) : "Authors not reported"}
      </div>
      {p.journal && <div className="text-sm italic text-muted-foreground">{p.journal}</div>}
      {p.abstract ? (
        <p className="text-sm mt-3 text-foreground/85">
          {more || p.abstract.length < 320 ? p.abstract : `${p.abstract.slice(0, 320)}… `}
          {p.abstract.length >= 320 && <button className="text-primary text-xs ml-1" onClick={() => setMore(!more)}>{more ? "less" : "more"}</button>}
        </p>
      ) : p.origin !== "upload" && <p className="text-xs mt-3 text-muted-foreground">No abstract returned by the source.</p>}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3">
        {p.doi && <a className="text-xs font-mono text-primary hover:underline" href={`https://doi.org/${p.doi}`} target="_blank" rel="noreferrer" data-testid="paper-doi">doi:{p.doi}</a>}
        {p.url && <a className="text-xs flex items-center gap-1 text-muted-foreground hover:text-foreground" href={p.url} target="_blank" rel="noreferrer"><ExternalLink size={12} />Link</a>}
        <OA p={p} />
      </div>
      {actions && <div className="flex flex-wrap gap-2 mt-4">{actions}</div>}
      {footer}
    </div>
  );
};
