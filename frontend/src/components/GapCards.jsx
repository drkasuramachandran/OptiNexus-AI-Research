import { AlertTriangle, BookOpen } from "lucide-react";

const TAG_STYLE = {
  "Directly reported limitation": "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  "Pattern inferred across studies": "bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30",
  "AI suggestion": "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
};
const STRENGTH = { High: "text-emerald-500", Medium: "text-sky-500", Low: "text-amber-500" };

const Row = ({ label, children }) => (
  <div><div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div><div className="text-sm mt-0.5">{children}</div></div>
);

export const GapCards = ({ gaps }) => (
  <div className="space-y-3 mt-2" data-testid="gap-cards">
    <div className="text-xs rounded-md border bg-muted/50 px-3 py-2" data-testid="gap-papers-analysed">
      Papers analysed: <b>{gaps.papers_analysed}</b> ({gaps.full_text_count} full text, {gaps.papers_analysed - gaps.full_text_count} abstract/metadata only)
    </div>
    {gaps.items.map((g, i) => (
      <div key={i} className="rounded-lg border bg-background p-4 space-y-2.5" data-testid={`gap-card-${i}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-semibold">{g.research_area}</h4>
          <span className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border ${TAG_STYLE[g.tag]}`} data-testid={`gap-tag-${i}`}>{g.tag}</span>
        </div>
        <Row label="Supporting papers">
          {g.supporting_papers.length ? (
            <ul className="space-y-0.5">{g.supporting_papers.map((p) => (
              <li key={p.id} className="flex gap-1.5"><BookOpen size={13} className="mt-1 shrink-0 text-primary" /><span>{p.title}{p.year ? ` (${p.year})` : ""} <span className="text-xs text-muted-foreground">· {p.basis}</span></span></li>
            ))}</ul>
          ) : <span className="text-muted-foreground italic">None — not directly supported by your papers</span>}
        </Row>
        <Row label="Limitations found">{g.limitations_found}</Row>
        <Row label="Unresolved questions">{g.unresolved_questions}</Row>
        <Row label="Proposed direction">{g.proposed_direction}</Row>
        <Row label="Evidence strength"><span className={`font-semibold ${STRENGTH[g.evidence_strength]}`} data-testid={`gap-strength-${i}`}>{g.evidence_strength}</span> — {g.strength_reason}</Row>
      </div>
    ))}
    <div className="flex gap-2 text-xs text-amber-700 dark:text-amber-300 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2" data-testid="gap-novelty-reminder">
      <AlertTriangle size={14} className="shrink-0 mt-0.5" />
      Verify novelty: these gaps are based only on the papers above. Run further literature and patent searches before claiming novelty.
    </div>
  </div>
);
