import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { formatApiError } from "@/lib/api";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  async function onSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email.trim().toLowerCase(), password);
      toast.success("Bem-vinda à Acorde");
      navigate("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-black grain">
      {/* Hero image side */}
      <div
        className="relative hidden lg:flex items-end p-12 overflow-hidden"
        style={{
          backgroundImage:
            "linear-gradient(180deg, rgba(0,0,0,0.2) 0%, rgba(0,0,0,0.85) 100%), url('https://images.unsplash.com/photo-1789655467818-d0bfa4e363ea?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1ODR8MHwxfHNlYXJjaHwzfHxhYnN0cmFjdCUyMHZpbnlsJTIwcmVjb3JkJTIwZGFyayUyMGJhY2tncm91bmR8ZW58MHx8fHwxNzkxMjMyOTU3fDA&ixlib=rb-4.1.0&q=85')",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 bg-[#FFD700] flex items-center justify-center">
              <span className="text-black font-black text-base">A</span>
            </div>
            <div className="font-extrabold text-2xl tracking-tight">ACORDE</div>
          </div>
          <h1 className="text-5xl font-extrabold leading-none max-w-md">
            Royalties, <span className="acorde-gradient-text">precisão</span> e repasse.
          </h1>
          <p className="text-neutral-400 mt-6 max-w-md text-sm">
            Processe relatórios Abramus Digital, calcule taxas administrativas e emita relatórios Acorde em PDF para suas editoras e autores — com total controle da operação.
          </p>
          <div className="mt-10 flex items-center gap-2 text-xs text-neutral-500 uppercase tracking-[0.3em]">
            <div className="w-6 h-[1px] bg-[#FFD700]" /> Administradora de Direitos Autorais
          </div>
        </div>
      </div>

      {/* Form side */}
      <div className="flex items-center justify-center px-6 py-12 bg-[#050505]">
        <div className="w-full max-w-md stagger-up">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-10 h-10 bg-[#FFD700] flex items-center justify-center">
              <span className="text-black font-black">A</span>
            </div>
            <div className="font-extrabold text-2xl tracking-tight">ACORDE</div>
          </div>

          <div className="mb-10">
            <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-3">Portal Acorde</div>
            <h2 className="text-4xl font-extrabold leading-tight">Acesse sua conta</h2>
            <p className="text-neutral-500 text-sm mt-3">
              Administradora ou editora cadastrada. Use o email e senha fornecidos pela equipe Acorde.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-5" data-testid="login-form">
            <div>
              <Label className="text-xs uppercase tracking-[0.2em] text-neutral-500 mb-2 block">Email</Label>
              <Input
                data-testid="login-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="voce@editora.com.br"
                className="h-12 bg-[#0F0F11] border-[#222] rounded-sm text-base focus:border-[#FFD700] focus:ring-1 focus:ring-[#FFD700]"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-[0.2em] text-neutral-500 mb-2 block">Senha</Label>
              <Input
                data-testid="login-password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="h-12 bg-[#0F0F11] border-[#222] rounded-sm text-base focus:border-[#FFD700] focus:ring-1 focus:ring-[#FFD700]"
              />
            </div>

            <Button
              data-testid="login-submit"
              type="submit"
              disabled={submitting}
              className="w-full h-12 bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm font-bold uppercase tracking-[0.15em] text-sm"
            >
              {submitting ? "Entrando..." : "Entrar no portal →"}
            </Button>
          </form>

          <div className="mt-10 pt-6 border-t border-[#1f1f1f] text-xs text-neutral-500">
            Problemas no acesso? Entre em contato com <span className="text-white">atendimento@acordemusica.com.br</span>.
          </div>
        </div>
      </div>
    </div>
  );
}
