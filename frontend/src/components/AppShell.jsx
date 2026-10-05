import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { LayoutDashboard, Upload, Building2, Mic2, FileBarChart, LogOut } from "lucide-react";

const navAll = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "editora"] },
  { to: "/uploads", label: "Uploads Abramus", icon: Upload, roles: ["admin"] },
  { to: "/editoras", label: "Editoras", icon: Building2, roles: ["admin"] },
  { to: "/autores", label: "Autores", icon: Mic2, roles: ["admin", "editora"] },
  { to: "/relatorios", label: "Relatórios", icon: FileBarChart, roles: ["admin", "editora"] },
];

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const nav = navAll.filter((n) => n.roles.includes(user?.role));

  return (
    <div className="min-h-screen flex bg-[#050505] text-white">
      <aside className="w-64 shrink-0 border-r border-[#1f1f1f] bg-[#070707] flex flex-col">
        <div className="px-6 pt-6 pb-8 border-b border-[#1f1f1f]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#FFD700] flex items-center justify-center">
              <span className="text-black font-black text-sm">A</span>
            </div>
            <div>
              <div className="font-extrabold tracking-tight text-lg leading-none">ACORDE</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-neutral-500 mt-1">Royalties</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-6 px-3 space-y-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, "-")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 text-sm rounded-sm border border-transparent ${
                  isActive
                    ? "bg-[#FFD700] text-black font-semibold"
                    : "text-neutral-400 hover:text-white hover:border-[#2a2a2a] hover:bg-[#101010]"
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-[#1f1f1f]">
          <div className="text-xs text-neutral-500 mb-2 uppercase tracking-wider">
            {user?.role === "admin" ? "Administrador" : "Editora"}
          </div>
          <div className="text-sm text-white truncate" title={user?.email}>{user?.name || user?.email}</div>
          <div className="text-xs text-neutral-500 truncate">{user?.email}</div>
          <button
            data-testid="logout-btn"
            onClick={async () => { await logout(); navigate("/login"); }}
            className="mt-3 w-full flex items-center justify-center gap-2 text-xs text-neutral-400 hover:text-[#FFD700] border border-[#1f1f1f] hover:border-[#FFD700] py-2"
          >
            <LogOut className="w-3.5 h-3.5" /> Sair
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        <header className="sticky top-0 z-20 h-14 bg-black/60 backdrop-blur-xl border-b border-[#1f1f1f] px-8 flex items-center justify-between">
          <div className="text-xs text-neutral-500 uppercase tracking-[0.3em]">
            Administradora de Direitos Autorais
          </div>
          <div className="text-xs text-neutral-500">
            {new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" })}
          </div>
        </header>
        <div className="px-8 py-8 max-w-[1500px]">{children}</div>
      </main>
    </div>
  );
}
