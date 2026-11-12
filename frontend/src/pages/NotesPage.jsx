import { useEffect, useState } from "react";
import NotesPanel from "@/components/NotesPanel";
import { PageHeader } from "@/components/common";
import { api } from "@/lib/api";

export default function NotesPage() {
  const [projects, setProjects] = useState(null);
  useEffect(() => { api.get("/projects").then((r) => setProjects(r.data)); }, []);
  return (
    <div>
      <PageHeader title="Notes" subtitle="Simple notes, optionally attached to a project." />
      {projects && <NotesPanel projects={projects} />}
    </div>
  );
}
