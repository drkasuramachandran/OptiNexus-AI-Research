import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const PageHeader = ({ title, subtitle, children }) => (
  <div className="flex flex-wrap items-end justify-between gap-4 mb-8 fade-up">
    <div>
      <h1 className="text-3xl sm:text-4xl font-semibold">{title}</h1>
      {subtitle && <p className="text-muted-foreground mt-2 text-sm sm:text-base">{subtitle}</p>}
    </div>
    <div className="flex gap-2 flex-wrap">{children}</div>
  </div>
);

export const Empty = ({ icon: Icon, title, text, children, testid }) => (
  <div data-testid={testid} className="border border-dashed rounded-lg py-12 px-6 text-center text-muted-foreground">
    {Icon && <Icon className="mx-auto mb-3 text-primary/70" size={28} />}
    <div className="font-medium text-foreground">{title}</div>
    {text && <p className="text-sm mt-1 max-w-md mx-auto">{text}</p>}
    {children && <div className="mt-4">{children}</div>}
  </div>
);

export const Panel = ({ className = "", children, ...rest }) => (
  <div className={`rounded-lg border bg-card p-5 ${className}`} {...rest}>{children}</div>
);

export const SOURCE_STYLE = {
  OpenAlex: "bg-orange-500/15 text-orange-600 dark:text-orange-300 border-orange-500/30",
  Crossref: "bg-sky-500/15 text-sky-600 dark:text-sky-300 border-sky-500/30",
  arXiv: "bg-rose-500/15 text-rose-600 dark:text-rose-300 border-rose-500/30",
  PubMed: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/30",
  Upload: "bg-primary/15 text-primary border-primary/30",
};

export const SourceBadge = ({ s }) => (
  <span data-testid={`source-badge-${s}`} className={`text-[10px] font-mono uppercase tracking-wide px-1.5 py-0.5 rounded border ${SOURCE_STYLE[s] || "bg-muted"}`}>{s}</span>
);

export const Md = ({ children }) => (
  <div className="prose-sci"><ReactMarkdown remarkPlugins={[remarkGfm]}>{children || ""}</ReactMarkdown></div>
);
