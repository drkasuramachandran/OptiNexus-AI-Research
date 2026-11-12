import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "next-themes";
import { LayoutDashboard, FolderKanban, Search, Library, FileText, Bot, StickyNote, Settings, Sun, Moon, LogOut, Menu, PenLine } from "lucide-react";
import { Logo, TAGLINE } from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  ["/", "Dashboard", LayoutDashboard, "dashboard"],
  ["/projects", "Projects", FolderKanban, "projects"],
  ["/search", "Literature Search", Search, "search"],
  ["/library", "Library", Library, "library"],
  ["/analyzer", "Paper Analyzer", FileText, "analyzer"],
  ["/assistant", "AI Assistant", Bot, "assistant"],
  ["/writing", "Writing Studio", PenLine, "writing"],
  ["/notes", "Notes", StickyNote, "notes"],
  ["/settings", "Settings", Settings, "settings"],
];

export default function Layout() {
  const { logout, user } = useAuth();
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen flex">
      <aside className={`fixed lg:sticky top-0 z-40 h-screen w-64 shrink-0 border-r bg-card flex flex-col transition-transform duration-200 ${open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}>
        <div className="flex items-center gap-3 px-5 py-5 border-b">
          <Logo />
          <div>
            <div className="font-display font-semibold leading-tight">OptiNexus AI</div>
            <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{TAGLINE}</div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV.map(([to, label, Icon, id]) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)} data-testid={`nav-${id}`}
              className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${isActive ? "bg-primary/15 text-primary font-medium" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}>
              <Icon size={17} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t space-y-1">
          <div className="px-3 py-1 text-xs text-muted-foreground truncate" data-testid="sidebar-user-email">{user?.email}</div>
          <button data-testid="theme-toggle" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />} {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <button data-testid="logout-button" onClick={logout}
            className="w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">
            <LogOut size={17} /> Sign out
          </button>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="flex-1 min-w-0">
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 border-b bg-card">
          <button data-testid="mobile-menu-button" onClick={() => setOpen(true)}><Menu /></button>
          <Logo size={28} /><span className="font-display font-semibold">OptiNexus AI</span>
        </header>
        <main className="p-4 sm:p-8 max-w-[1400px] mx-auto"><Outlet /></main>
      </div>
    </div>
  );
}
