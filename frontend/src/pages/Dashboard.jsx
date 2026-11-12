import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { FolderPlus, Search, Upload, FolderKanban, BookOpen, FileText, StickyNote, Activity, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel, Empty } from "@/components/common";
import { TAGLINE } from "@/components/Logo";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const Stat = ({ icon: Icon, label, value, testid }) => (
  <Panel className="flex items-center gap-4">
    <div className="p-2.5 rounded-md bg-primary/12 text-primary bg-primary/10"><Icon size={20} /></div>
    <div><div className="text-2xl font-display font-semibold" data-testid={testid}>{value}</div><div className="text-xs text-muted-foreground">{label}</div></div>
  </Panel>
);

const ChartCard = ({ title, data, x, testid }) => (
  <Panel data-testid={testid}>
    <h3 className="font-semibold mb-4">{title}</h3>
    {data.length === 0 ? (
      <Empty icon={BarChart3} title="No data yet" text="Save or upload papers to see this chart. It is computed only from your stored papers." />
    ) : (
      <div className="h-64">
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey={x} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} width={30} />
            <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} cursor={{ fill: "hsl(var(--muted))" }} />
            <Bar dataKey="count" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    )}
  </Panel>
);

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/dashboard").then((r) => setD(r.data)); }, []);

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.name || "researcher"}`} subtitle={TAGLINE}>
        <Button data-testid="quick-new-project" onClick={() => nav("/projects?new=1")}><FolderPlus size={16} className="mr-1.5" />New project</Button>
        <Button data-testid="quick-search" variant="outline" onClick={() => nav("/search")}><Search size={16} className="mr-1.5" />Search literature</Button>
        <Button data-testid="quick-upload" variant="outline" onClick={() => nav("/analyzer")}><Upload size={16} className="mr-1.5" />Upload PDFs</Button>
      </PageHeader>
      {!d ? <div className="text-muted-foreground">Loading…</div> : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat icon={FolderKanban} label="Projects" value={d.project_count} testid="stat-projects" />
            <Stat icon={BookOpen} label="Saved papers" value={d.paper_count} testid="stat-papers" />
            <Stat icon={FileText} label="Uploaded PDFs" value={d.upload_count} testid="stat-uploads" />
            <Stat icon={StickyNote} label="Notes" value={d.note_count} testid="stat-notes" />
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <ChartCard title="Papers by year" data={d.papers_by_year} x="year" testid="chart-papers-by-year" />
            <ChartCard title="Papers by source" data={d.papers_by_source} x="source" testid="chart-papers-by-source" />
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <Panel>
              <h3 className="font-semibold mb-4">Active projects</h3>
              {d.projects.length === 0 ? <Empty icon={FolderKanban} title="No projects yet" text="Create a project to organise papers, notes and AI chats." /> : (
                <div className="space-y-2" data-testid="dashboard-projects">
                  {d.projects.map((p) => (
                    <Link key={p.id} to={`/projects/${p.id}`} className="block rounded-md border p-3 hover:border-primary/50 transition-colors">
                      <div className="font-medium">{p.title}</div>
                      {p.objectives && <div className="text-xs text-muted-foreground line-clamp-1 mt-0.5">{p.objectives}</div>}
                    </Link>
                  ))}
                </div>
              )}
            </Panel>
            <Panel>
              <h3 className="font-semibold mb-4">Recent activity</h3>
              {d.activity.length === 0 ? <Empty icon={Activity} title="No activity yet" /> : (
                <ul className="space-y-3" data-testid="dashboard-activity">
                  {d.activity.map((a) => (
                    <li key={a.id} className="flex gap-3 text-sm">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                      <div><div>{a.text}</div><div className="text-xs text-muted-foreground font-mono">{new Date(a.created_at).toLocaleString()}</div></div>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
