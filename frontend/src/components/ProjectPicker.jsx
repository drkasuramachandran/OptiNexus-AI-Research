import { FolderPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger, DropdownMenuCheckboxItem } from "@/components/ui/dropdown-menu";

// Single action: pick one project. Multi: toggle linked projects.
export const ProjectPicker = ({ projects, onPick, selected, label = "Add to project", testid }) => (
  <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button size="sm" variant="outline" data-testid={testid}><FolderPlus size={14} className="mr-1" />{label}</Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end" className="w-60">
      <DropdownMenuLabel>Projects</DropdownMenuLabel>
      {projects.length === 0 && <div className="px-2 py-2 text-xs text-muted-foreground">No projects yet — create one in Projects.</div>}
      {projects.map((p) =>
        selected ? (
          <DropdownMenuCheckboxItem key={p.id} checked={selected.includes(p.id)} onCheckedChange={() => onPick(p.id)} data-testid={`project-option-${p.id}`}>
            {p.title}
          </DropdownMenuCheckboxItem>
        ) : (
          <DropdownMenuItem key={p.id} onClick={() => onPick(p.id)} data-testid={`project-option-${p.id}`}>{p.title}</DropdownMenuItem>
        )
      )}
    </DropdownMenuContent>
  </DropdownMenu>
);
