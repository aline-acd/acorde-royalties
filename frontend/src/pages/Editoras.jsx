import { useEffect, useRef, useState } from "react";
import { api, API, formatApiError, formatPct } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, Upload, KeyRound, RefreshCw, FileDown, AlertCircle } from "lucide-react";

export default function Editoras() {
  const [editoras, setEditoras] = useState([]);
  const [filter, setFilter] = useState("all"); // all | pending | configured
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", cnpj: "", admin_fee_percent: 0, email: "" });
  const [loginEditora, setLoginEditora] = useState(null);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const bulkRef = useRef(null);
  const [syncing, setSyncing] = useState(false);

  async function refresh() {
    const { data } = await api.get("/editoras");
    setEditoras(data || []);
  }
  useEffect(() => { refresh(); }, []);

  async function syncFromReports() {
    setSyncing(true);
    try {
      const { data } = await api.post("/discover/sync");
      toast.success(`${data.new_editoras} editoras e ${data.new_autores} autores importados dos relatórios`);
      refresh();
    } catch (e) { toast.error(formatApiError(e)); } finally { setSyncing(false); }
  }

  async function downloadPendingCsv() {
    try {
      const res = await api.get("/discover/pending/editoras.csv", { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      a.download = "acorde_editoras_pendentes.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast.success("CSV pendentes baixado");
    } catch (e) { toast.error(formatApiError(e)); }
  }

  const visible = editoras.filter((e) => {
    if (filter === "pending") return e.needs_review;
    if (filter === "configured") return !e.needs_review;
    return true;
  });

  const pendingCount = editoras.filter((e) => e.needs_review).length;

  function openNew() {
    setEditing(null);
    setForm({ name: "", cnpj: "", admin_fee_percent: 0, email: "" });
    setOpen(true);
  }

  function openEdit(e) {
    setEditing(e);
    setForm({ name: e.name, cnpj: e.cnpj || "", admin_fee_percent: e.admin_fee_percent || 0, email: e.email || "" });
    setOpen(true);
  }

  async function save() {
    try {
      if (editing) {
        await api.patch(`/editoras/${editing.id}`, {
          ...form,
          admin_fee_percent: Number(form.admin_fee_percent || 0),
        });
        toast.success("Editora atualizada");
      } else {
        await api.post("/editoras", { ...form, admin_fee_percent: Number(form.admin_fee_percent || 0) });
        toast.success("Editora cadastrada");
      }
      setOpen(false);
      refresh();
    } catch (e) { toast.error(formatApiError(e)); }
  }

  async function remove(id) {
    if (!window.confirm("Remover esta editora?")) return;
    try { await api.delete(`/editoras/${id}`); refresh(); } catch (e) { toast.error(formatApiError(e)); }
  }

  async function bulkCsv(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/editoras/bulk", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${data.created} criadas, ${data.updated} atualizadas`);
      refresh();
    } catch (e) { toast.error(formatApiError(e)); }
  }

  async function createLogin() {
    try {
      await api.post(`/editoras/${loginEditora.id}/login`, {
        editora_id: loginEditora.id,
        email: loginForm.email,
        password: loginForm.password,
      });
      toast.success("Login criado para a editora");
      setLoginEditora(null);
      setLoginForm({ email: "", password: "" });
      refresh();
    } catch (e) { toast.error(formatApiError(e)); }
  }

  return (
    <div className="space-y-10">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-2">Clientes</div>
          <h1 className="text-5xl font-extrabold leading-none">Editoras</h1>
          <p className="text-neutral-500 mt-3 text-sm max-w-2xl">
            Cadastre as editoras (clientes Acorde) e defina a taxa administrativa cobrada por cada uma.
            Editoras encontradas nos relatórios Abramus são importadas automaticamente como <span className="text-[#FFD700]">pendentes</span>.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button data-testid="sync-reports-btn" variant="outline" disabled={syncing} onClick={syncFromReports} className="h-11 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700]">
            <RefreshCw className={`w-4 h-4 mr-2 ${syncing ? "animate-spin" : ""}`} /> Sincronizar dos relatórios
          </Button>
          <Button data-testid="download-pending-editoras" variant="outline" onClick={downloadPendingCsv} className="h-11 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700]">
            <FileDown className="w-4 h-4 mr-2" /> CSV pendentes
          </Button>
          <input ref={bulkRef} type="file" className="hidden" accept=".csv" onChange={(e) => bulkCsv(e.target.files?.[0])} data-testid="bulk-editoras-file" />
          <Button data-testid="bulk-editoras-btn" variant="outline" className="h-11 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700]" onClick={() => bulkRef.current?.click()}>
            <Upload className="w-4 h-4 mr-2" /> Importar CSV
          </Button>
          <Button data-testid="new-editora-btn" onClick={openNew} className="h-11 bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm font-semibold uppercase tracking-wider text-xs px-5">
            <Plus className="w-4 h-4 mr-2" /> Nova editora
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setFilter("all")}
          data-testid="filter-all"
          className={`px-3 py-1.5 text-xs uppercase tracking-wider rounded-sm border ${filter === "all" ? "bg-[#FFD700] text-black border-[#FFD700]" : "border-[#2a2a2a] text-neutral-400 hover:border-[#FFD700] hover:text-[#FFD700]"}`}
        >
          Todas <span className="opacity-70 ml-1">({editoras.length})</span>
        </button>
        <button
          onClick={() => setFilter("pending")}
          data-testid="filter-pending"
          className={`px-3 py-1.5 text-xs uppercase tracking-wider rounded-sm border inline-flex items-center gap-1.5 ${filter === "pending" ? "bg-[#FFD700] text-black border-[#FFD700]" : "border-[#2a2a2a] text-neutral-400 hover:border-[#FFD700] hover:text-[#FFD700]"}`}
        >
          <AlertCircle className="w-3.5 h-3.5" />
          Pendentes <span className="opacity-70 ml-1">({pendingCount})</span>
        </button>
        <button
          onClick={() => setFilter("configured")}
          data-testid="filter-configured"
          className={`px-3 py-1.5 text-xs uppercase tracking-wider rounded-sm border ${filter === "configured" ? "bg-[#FFD700] text-black border-[#FFD700]" : "border-[#2a2a2a] text-neutral-400 hover:border-[#FFD700] hover:text-[#FFD700]"}`}
        >
          Configuradas <span className="opacity-70 ml-1">({editoras.length - pendingCount})</span>
        </button>
      </div>

      <div className="border border-[#1f1f1f] rounded-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#0F0F11] text-neutral-500 text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left px-4 py-3">Nome</th>
              <th className="text-left px-4 py-3">CNPJ</th>
              <th className="text-right px-4 py-3">Taxa Admin.</th>
              <th className="text-left px-4 py-3">Email / Login</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr><td colSpan={5} className="text-center text-neutral-600 py-10">Nenhuma editora.</td></tr>
            )}
            {visible.map((e) => (
              <tr key={e.id} className="border-t border-[#1a1a1a] hover:bg-[#0b0b0b]">
                <td className="px-4 py-3 text-white">
                  <div className="flex items-center gap-2">
                    <span>{e.name}</span>
                    {e.needs_review && (
                      <span data-testid={`pending-badge-${e.id}`} className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider bg-[#FFD700]/15 text-[#FFD700] border border-[#FFD700]/30 px-2 py-0.5 rounded-sm">
                        <AlertCircle className="w-3 h-3" /> Pendente
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-neutral-400 mono text-xs">{e.cnpj || "—"}</td>
                <td className="px-4 py-3 text-right mono text-[#FFD700]">{formatPct(e.admin_fee_percent)}</td>
                <td className="px-4 py-3 text-neutral-400 text-xs">
                  {e.email || "—"}
                  {e.has_login && <span className="ml-2 inline-block text-[10px] uppercase tracking-wider text-black bg-[#FFD700] px-2 py-0.5 rounded-sm">com login</span>}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button data-testid={`login-editora-${e.id}`} onClick={() => { setLoginEditora(e); setLoginForm({ email: e.email || "", password: "" }); }} title="Criar login editora" className="text-neutral-500 hover:text-[#FFD700] p-2">
                    <KeyRound className="w-4 h-4" />
                  </button>
                  <button data-testid={`edit-editora-${e.id}`} onClick={() => openEdit(e)} className="text-neutral-500 hover:text-white p-2">
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button data-testid={`delete-editora-${e.id}`} onClick={() => remove(e.id)} className="text-neutral-500 hover:text-red-400 p-2">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-neutral-600">
        Formato do CSV de importação: colunas <span className="mono text-neutral-400">nome,cnpj,taxa_admin,email</span> (taxa em %, ex: 10 para 10%).
      </p>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0a0a0a] border-[#1f1f1f] text-white rounded-sm">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">{editing ? "Editar editora" : "Nova editora"}</DialogTitle>
            <DialogDescription className="text-xs text-neutral-500">
              O nome da editora precisa ser idêntico ao campo TITULAR dos relatórios Abramus para o casamento automático dos dados.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <Field label="Nome (deve bater com o TITULAR dos relatórios Abramus)">
              <Input data-testid="editora-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm" />
            </Field>
            <Field label="CNPJ">
              <Input data-testid="editora-cnpj" value={form.cnpj} onChange={(e) => setForm({ ...form, cnpj: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm" />
            </Field>
            <Field label="Taxa administrativa (%)">
              <Input data-testid="editora-taxa" type="number" step="0.01" value={form.admin_fee_percent} onChange={(e) => setForm({ ...form, admin_fee_percent: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm mono" />
            </Field>
            <Field label="Email de contato (opcional)">
              <Input data-testid="editora-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm" />
            </Field>
          </div>
          <DialogFooter className="mt-6">
            <Button variant="ghost" onClick={() => setOpen(false)} className="text-neutral-400">Cancelar</Button>
            <Button data-testid="save-editora" onClick={save} className="bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm">Salvar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!loginEditora} onOpenChange={(v) => !v && setLoginEditora(null)}>
        <DialogContent className="bg-[#0a0a0a] border-[#1f1f1f] text-white rounded-sm">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">Criar login — {loginEditora?.name}</DialogTitle>
            <DialogDescription className="text-xs text-neutral-500">
              A editora acessará um portal próprio e visualizará somente seus próprios autores e relatórios.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <Field label="Email de login">
              <Input data-testid="editora-login-email" value={loginForm.email} onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm" />
            </Field>
            <Field label="Senha">
              <Input data-testid="editora-login-password" type="password" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm" />
            </Field>
            <p className="text-xs text-neutral-500">A editora poderá entrar no portal com essas credenciais e visualizar somente seus próprios relatórios.</p>
          </div>
          <DialogFooter className="mt-6">
            <Button variant="ghost" onClick={() => setLoginEditora(null)} className="text-neutral-400">Cancelar</Button>
            <Button data-testid="save-editora-login" onClick={createLogin} className="bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm">Salvar login</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <Label className="text-xs uppercase tracking-[0.2em] text-neutral-500 mb-2 block">{label}</Label>
      {children}
    </div>
  );
}
