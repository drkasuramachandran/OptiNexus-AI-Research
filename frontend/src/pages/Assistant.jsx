import { useEffect, useState } from "react";
import ChatWorkspace from "@/components/ChatWorkspace";
import { PageHeader } from "@/components/common";
import { api } from "@/lib/api";

export default function Assistant() {
  const [projects, setProjects] = useState(null);
  useEffect(() => { api.get("/projects").then((r) => setProjects(r.data)); }, []);
  return (
    <div>
      <PageHeader title="AI Research Assistant" subtitle="One agent engine, five modes. Grounded in your saved papers and uploaded PDFs — never fabricated references." />
      {projects && <ChatWorkspace projects={projects} />}
    </div>
  );
}
