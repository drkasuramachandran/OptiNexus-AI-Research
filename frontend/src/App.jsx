import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import AuthPage from "@/pages/AuthPage";
import Dashboard from "@/pages/Dashboard";
import Projects from "@/pages/Projects";
import ProjectDetail from "@/pages/ProjectDetail";
import SearchPage from "@/pages/SearchPage";
import LibraryPage from "@/pages/LibraryPage";
import Analyzer from "@/pages/Analyzer";
import Assistant from "@/pages/Assistant";
import WritingStudio from "@/pages/WritingStudio";
import NotesPage from "@/pages/NotesPage";
import SettingsPage from "@/pages/SettingsPage";

const Protected = ({ children }) => {
  const { user } = useAuth();
  if (user === null) return <div className="min-h-screen grid place-items-center text-muted-foreground">Loading…</div>;
  return user ? children : <Navigate to="/login" replace />;
};

const PublicOnly = ({ children }) => {
  const { user } = useAuth();
  if (user === null) return null;
  return user ? <Navigate to="/" replace /> : children;
};

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<PublicOnly><AuthPage mode="login" /></PublicOnly>} />
            <Route path="/register" element={<PublicOnly><AuthPage mode="register" /></PublicOnly>} />
            <Route element={<Protected><Layout /></Protected>}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/projects/:id" element={<ProjectDetail />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/library" element={<LibraryPage />} />
              <Route path="/analyzer" element={<Analyzer />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/writing" element={<WritingStudio />} />
              <Route path="/notes" element={<NotesPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="bottom-right" />
      </AuthProvider>
    </ThemeProvider>
  );
}
