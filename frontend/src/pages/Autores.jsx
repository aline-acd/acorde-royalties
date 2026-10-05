import { useEffect, useRef, useState } from "react";
import { api, formatApiError, formatPct } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, Upload } from "lucide-react";

export default function Autores() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [autores, setAutores] = useState([]);
  const [editoras, setEditoras] = useState([]);
  const [filterEditora, setFilterEditora] = useState("__all__");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", editora_id: "", admin_fee_percent: 0 });
  const bulkRef = useRef(null);

  async function refresh() {
    const params = filterEditora && filterEditora !== "__all__" ? { editora_id: filterEditora } : {};
    const { data } = await api.get("/autores", { params });
    setAutores(data || []);
  }

  useEffect(() => {
    api.get("/editoras").then((r) => setEditoras(r.data || []));
  }, []);
  useEffect(() => { refresh(); }, [filterEditora]);

  function openNew() {
    setEditing(null);
    setForm({ name: "", editora_id: filterEditora !== "__all__" ? filterEditora : "", admin_fee_percent: 0 });
    setOpen(true);
  }
  function openEdit(a) {
    setEditing(a);
    setForm({ name: a.name, editora_id: a.editora_id || "", admin_fee_percent: a.admin_fee_percent || 0 });
    setOpen(true);
  }

  async function save() {
    try {
      const payload = { ...form, admin_fee_percent: Number(form.admin_fee_percent || 0), editora_id: form.editora_id || null };
      if (editing) {
        await api.patch(`/autores/${editing.id}`, payload);
        toast.success("Autor atualizado");
      } else {
        await api.post("/autores", payload);
        toast.success("Autor cadastrado");
      }
      setOpen(false);
      refresh();
    } catch (e) { toast.error(formatApiError(e)); }
  }

  async function remove(id) {
    if (!window.confirm("Remover este autor?")) return;
    try { await api.delete(`/autores/${id}`); refresh(); } catch (e) { toast.error(formatApiError(e)); }
  }

  async function bulkCsv(file) {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/autores/bulk", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${data.created} criados, ${data.updated} atualizados, ${data.skipped} ignorados`);
      refresh();
    } catch (e) { toast.error(formatApiError(e)); }
  }

  return (
    <div className="space-y-10">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-2">Catálogo</div>
          <h1 className="text-5xl font-extrabold leading-none">Autores</h1>
          <p className="text-neutral-500 mt-3 text-sm max-w-2xl">
            {isAdmin
              ? "Cadastre autores e configure a taxa administrativa individual. Nomes devem bater com os nomes do relatório Abramus."
              : "Autores vinculados à sua editora."}
          </p>
        </div>
        {isAdmin && (
          <div className="flex items-center gap-3">
            <input ref={bulkRef} type="file" className="hidden" accept=".csv" onChange={(e) => bulkCsv(e.target.files?.[0])} data-testid="bulk-autores-file" />
            <Button data-testid="bulk-autores-btn" variant="outline" className="h-11 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700]" onClick={() => bulkRef.current?.click()}>
              <Upload className="w-4 h-4 mr-2" /> Importar CSV
            </Button>
            <Button data-testid="new-autor-btn" onClick={openNew} className="h-11 bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm font-semibold uppercase tracking-wider text-xs px-5">
              <Plus className="w-4 h-4 mr-2" /> Novo autor
            </Button>
          </div>
        )}
      </div>

      {isAdmin && (
        <div className="flex items-center gap-3">
          <div className="text-xs uppercase tracking-[0.2em] text-neutral-500">Filtrar editora</div>
          <Select value={filterEditora} onValueChange={setFilterEditora}>
            <SelectTrigger data-testid="filter-editora" className="w-72 h-10 bg-[#0F0F11] border-[#222] rounded-sm text-white">
              <SelectValue placeholder="Todas" />
            </SelectTrigger>
            <SelectContent className="bg-[#0F0F11] border-[#222] text-white max-h-72">
              <SelectItem value="__all__">Todas as editoras</SelectItem>
              {editoras.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="border border-[#1f1f1f] rounded-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#0F0F11] text-neutral-500 text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left px-4 py-3">Autor</th>
              <th className="text-left px-4 py-3">Editora</th>
              {isAdmin && <th className="text-right px-4 py-3">Taxa Admin.</th>}
              {isAdmin && <th className="px-4 py-3"></th>}
            </tr>
          </thead>
          <tbody>
            {autores.length === 0 && (
              <tr><td colSpan={isAdmin ? 4 : 2} className="text-center text-neutral-600 py-10">Nenhum autor.</td></tr>
            )}
            {autores.map((a) => (
              <tr key={a.id} className="border-t border-[#1a1a1a] hover:bg-[#0b0b0b]">
                <td className="px-4 py-3 text-white">{a.name}</td>
                <td className="px-4 py-3 text-neutral-400">{a.editora_name || "—"}</td>
                {isAdmin && <td className="px-4 py-3 text-right mono text-[#FFD700]">{formatPct(a.admin_fee_percent)}</td>}
                {isAdmin && (
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <button data-testid={`edit-autor-${a.id}`} onClick={() => openEdit(a)} className="text-neutral-500 hover:text-white p-2">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button data-testid={`delete-autor-${a.id}`} onClick={() => remove(a.id)} className="text-neutral-500 hover:text-red-400 p-2">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {isAdmin && (
        <p className="text-xs text-neutral-600">
          Formato do CSV: colunas <span className="mono text-neutral-400">nome,editora,taxa_admin</span>. A coluna "editora" deve bater com o nome cadastrado.
        </p>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0a0a0a] border-[#1f1f1f] text-white rounded-sm">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">{editing ? "Editar autor" : "Novo autor"}</DialogTitle>
            <DialogDescription className="text-xs text-neutral-500">
              O nome do autor precisa bater com a coluna NOME do relatório Autor Abramus para o cruzamento automático.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <Field label="Nome do autor (deve bater com o NOME do relatório Abramus)">
              <Input data-testid="autor-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm" />
            </Field>
            <Field label="Editora">
              <Select value={form.editora_id || "__none__"} onValueChange={(v) => setForm({ ...form, editora_id: v === "__none__" ? "" : v })}>
                <SelectTrigger data-testid="autor-editora" className="bg-[#0F0F11] border-[#222] rounded-sm">
                  <SelectValue placeholder="Selecionar..." />
                </SelectTrigger>
                <SelectContent className="bg-[#0F0F11] border-[#222] text-white max-h-72">
                  <SelectItem value="__none__">Sem editora vinculada</SelectItem>
                  {editoras.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Taxa administrativa (%) — não aparecerá no PDF do autor">
              <Input data-testid="autor-taxa" type="number" step="0.01" value={form.admin_fee_percent} onChange={(e) => setForm({ ...form, admin_fee_percent: e.target.value })} className="bg-[#0F0F11] border-[#222] rounded-sm mono" />
            </Field>
          </div>
          <DialogFooter className="mt-6">
            <Button variant="ghost" onClick={() => setOpen(false)} className="text-neutral-400">Cancelar</Button>
            <Button data-testid="save-autor" onClick={save} className="bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm">Salvar</Button>
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
