import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Toaster } from "sonner";
import LoginPage from "@/pages/Login";
import DashboardPage from "@/pages/Dashboard";
import UploadsPage from "@/pages/Uploads";
import EditorasPage from "@/pages/Editoras";
import AutoresPage from "@/pages/Autores";
import ReportsPage from "@/pages/Reports";
import AppShell from "@/components/AppShell";

function Private({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-neutral-500">Carregando...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

function RedirectRoot() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to="/dashboard" replace />;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster theme="dark" position="top-right" richColors closeButton />
          <Routes>
            <Route path="/" element={<RedirectRoot />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<Private><DashboardPage /></Private>} />
            <Route path="/uploads" element={<Private><UploadsPage /></Private>} />
            <Route path="/editoras" element={<Private><EditorasPage /></Private>} />
            <Route path="/autores" element={<Private><AutoresPage /></Private>} />
            <Route path="/relatorios" element={<Private><ReportsPage /></Private>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
