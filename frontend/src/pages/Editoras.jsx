import { useEffect, useRef, useState } from "react";
import { api, formatApiError, formatPct } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, Upload, KeyRound } from "lucide-react";

export default function Editoras() {
  const [editoras, setEditoras] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", cnpj: "", admin_fee_percent: 0, email: "" });
  const [loginEditora, setLoginEditora] = useState(null);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const bulkRef = useRef(null);

  async function refresh() {
    const { data } = await api.get("/editoras");
    setEditoras(data || []);
  }
  useEffect(() => { refresh(); }, []);

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
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input ref={bulkRef} type="file" className="hidden" accept=".csv" onChange={(e) => bulkCsv(e.target.files?.[0])} data-testid="bulk-editoras-file" />
          <Button data-testid="bulk-editoras-btn" variant="outline" className="h-11 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700]" onClick={() => bulkRef.current?.click()}>
            <Upload className="w-4 h-4 mr-2" /> Importar CSV
          </Button>
          <Button data-testid="new-editora-btn" onClick={openNew} className="h-11 bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm font-semibold uppercase tracking-wider text-xs px-5">
            <Plus className="w-4 h-4 mr-2" /> Nova editora
          </Button>
        </div>
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
            {editoras.length === 0 && (
              <tr><td colSpan={5} className="text-center text-neutral-600 py-10">Nenhuma editora cadastrada.</td></tr>
            )}
            {editoras.map((e) => (
              <tr key={e.id} className="border-t border-[#1a1a1a] hover:bg-[#0b0b0b]">
                <td className="px-4 py-3 text-white">{e.name}</td>
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
