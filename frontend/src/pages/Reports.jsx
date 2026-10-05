import { useEffect, useState } from "react";
import { api, API, formatCurrency, formatNumber, formatPct, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Download, Package, Mail, CheckCircle2, Clock } from "lucide-react";

export default function Reports() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [tab, setTab] = useState(isAdmin ? "editora" : "autor");
  const [competencias, setCompetencias] = useState([]);
  const [competencia, setCompetencia] = useState("");
  const [editoras, setEditoras] = useState([]);
  const [autores, setAutores] = useState([]);
  const [selectedEditora, setSelectedEditora] = useState("");
  const [selectedAutor, setSelectedAutor] = useState("");
  const [reportEditora, setReportEditora] = useState(null);
  const [reportAutor, setReportAutor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [repasses, setRepasses] = useState({});
  const [notifOpen, setNotifOpen] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);

  useEffect(() => {
    api.get("/competencias").then((r) => setCompetencias(r.data || []));
    api.get("/editoras").then((r) => {
      setEditoras(r.data || []);
      if (!isAdmin && r.data?.[0]) setSelectedEditora(r.data[0].id);
    });
    api.get("/autores").then((r) => setAutores(r.data || []));
  }, []);

  useEffect(() => {
    // reload repasses whenever competencia changes
    api.get("/repasses", { params: competencia ? { competencia } : {} })
      .then((r) => {
        const map = {};
        (r.data || []).forEach((it) => { map[`${it.scope}:${it.scope_id}:${it.competencia}`] = it; });
        setRepasses(map);
      })
      .catch(() => {});
  }, [competencia]);

  async function loadEditora() {
    if (!selectedEditora) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/reports/editora/${selectedEditora}`, {
        params: competencia ? { competencia } : {},
      });
      setReportEditora(data);
    } catch (e) { toast.error(formatApiError(e)); } finally { setLoading(false); }
  }

  async function loadAutor() {
    if (!selectedAutor) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/reports/autor/${selectedAutor}`, {
        params: competencia ? { competencia } : {},
      });
      setReportAutor(data);
    } catch (e) { toast.error(formatApiError(e)); } finally { setLoading(false); }
  }

  async function downloadPdf(kind, id) {
    try {
      const url = `${API}/reports/${kind}/${id}/pdf${competencia ? `?competencia=${encodeURIComponent(competencia)}` : ""}`;
      const res = await api.get(url.replace(API, ""), { responseType: "blob" });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `Acorde_${kind}_${id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast.success("PDF gerado");
    } catch (e) { toast.error(formatApiError(e)); }
  }

  async function downloadBulkZip(scope) {
    setBulkBusy(true);
    try {
      const path = `/reports/bulk/${scope}/pdf${competencia ? `?competencia=${encodeURIComponent(competencia)}` : ""}`;
      const res = await api.get(path, { responseType: "blob" });
      const blob = new Blob([res.data], { type: "application/zip" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `Acorde_Relatorios_${scope}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast.success("ZIP gerado — baixado");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBulkBusy(false);
    }
  }

  async function toggleRepasse(scope, scopeId, nextStatus, valor, observacao) {
    if (!competencia) {
      toast.error("Selecione uma competência para gravar o repasse");
      return;
    }
    try {
      const payload = {
        scope,
        scope_id: scopeId,
        competencia,
        status: nextStatus,
        valor: Number(valor || 0),
        observacao: observacao || "",
        data_pagamento: nextStatus === "pago" ? new Date().toISOString().slice(0, 10) : null,
      };
      const { data } = await api.post("/repasses", payload);
      setRepasses({ ...repasses, [`${scope}:${scopeId}:${competencia}`]: data });
      toast.success(`Repasse marcado como ${nextStatus === "pago" ? "PAGO" : "pendente"}`);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  }

  return (
    <div className="space-y-10">
      <div>
        <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-2">Relatórios Acorde</div>
        <h1 className="text-5xl font-extrabold leading-none">Visualize & exporte</h1>
        <p className="text-neutral-500 mt-3 text-sm max-w-2xl">
          Gere relatórios Acorde individuais a partir dos dados Abramus processados. Exporte em PDF modelo Acorde.
        </p>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="text-xs uppercase tracking-[0.2em] text-neutral-500">Competência</div>
        <Select value={competencia || "__all__"} onValueChange={(v) => setCompetencia(v === "__all__" ? "" : v)}>
          <SelectTrigger data-testid="reports-competencia" className="w-64 h-10 bg-[#0F0F11] border-[#222] rounded-sm text-white">
            <SelectValue placeholder="Todas" />
          </SelectTrigger>
          <SelectContent className="bg-[#0F0F11] border-[#222] text-white">
            <SelectItem value="__all__">Todas as competências</SelectItem>
            {competencias.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>

        {isAdmin && (
          <div className="flex items-center gap-2 ml-auto">
            <Button
              data-testid="bulk-zip-editoras"
              onClick={() => downloadBulkZip("editora")}
              disabled={bulkBusy}
              variant="outline"
              className="h-10 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700] text-xs uppercase tracking-wider"
            >
              <Package className="w-4 h-4 mr-2" /> ZIP Editoras
            </Button>
            <Button
              data-testid="bulk-zip-autores"
              onClick={() => downloadBulkZip("autor")}
              disabled={bulkBusy}
              variant="outline"
              className="h-10 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700] text-xs uppercase tracking-wider"
            >
              <Package className="w-4 h-4 mr-2" /> ZIP Autores
            </Button>
            <Button
              data-testid="bulk-zip-both"
              onClick={() => downloadBulkZip("both")}
              disabled={bulkBusy || !competencia}
              className="h-10 bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm text-xs uppercase tracking-wider font-semibold"
              title={!competencia ? "Selecione uma competência" : ""}
            >
              <Package className="w-4 h-4 mr-2" /> {bulkBusy ? "Gerando..." : "ZIP Competência"}
            </Button>
            <Button
              data-testid="open-notifications"
              onClick={() => setNotifOpen(true)}
              disabled={!competencia}
              variant="outline"
              className="h-10 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700] text-xs uppercase tracking-wider"
            >
              <Mail className="w-4 h-4 mr-2" /> Notificar
            </Button>
          </div>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-[#0F0F11] border border-[#222] rounded-sm">
          <TabsTrigger value="editora" data-testid="tab-editora" className="data-[state=active]:bg-[#FFD700] data-[state=active]:text-black rounded-sm uppercase tracking-wider text-xs px-6">
            Relatório Editora
          </TabsTrigger>
          <TabsTrigger value="autor" data-testid="tab-autor" className="data-[state=active]:bg-[#FFD700] data-[state=active]:text-black rounded-sm uppercase tracking-wider text-xs px-6">
            Relatório Autor
          </TabsTrigger>
        </TabsList>

        <TabsContent value="editora" className="mt-6 space-y-6">
          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[280px]">
              <div className="text-xs uppercase tracking-[0.2em] text-neutral-500 mb-2">Editora</div>
              <Select value={selectedEditora} onValueChange={setSelectedEditora}>
                <SelectTrigger data-testid="select-editora" className="h-11 bg-[#0F0F11] border-[#222] rounded-sm text-white">
                  <SelectValue placeholder="Escolha uma editora..." />
                </SelectTrigger>
                <SelectContent className="bg-[#0F0F11] border-[#222] text-white max-h-80">
                  {editoras.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button data-testid="load-editora" onClick={loadEditora} className="h-11 bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm uppercase tracking-wider font-semibold text-xs px-6">
              Gerar relatório
            </Button>
            {reportEditora && (
              <Button data-testid="pdf-editora" onClick={() => downloadPdf("editora", reportEditora.editora.id)} variant="outline" className="h-11 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700]">
                <Download className="w-4 h-4 mr-2" /> Baixar PDF Acorde
              </Button>
            )}
          </div>

          {loading && <div className="text-neutral-500">Carregando...</div>}
          {reportEditora && (
            <>
              <EditoraReportView data={reportEditora} />
              {isAdmin && (
                <RepasseWidget
                  scope="editora"
                  scopeId={reportEditora.editora.id}
                  competencia={competencia}
                  record={repasses[`editora:${reportEditora.editora.id}:${competencia}`]}
                  defaultValor={reportEditora.totals.liquido}
                  onToggle={toggleRepasse}
                />
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="autor" className="mt-6 space-y-6">
          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[280px]">
              <div className="text-xs uppercase tracking-[0.2em] text-neutral-500 mb-2">Autor</div>
              <Select value={selectedAutor} onValueChange={setSelectedAutor}>
                <SelectTrigger data-testid="select-autor" className="h-11 bg-[#0F0F11] border-[#222] rounded-sm text-white">
                  <SelectValue placeholder="Escolha um autor..." />
                </SelectTrigger>
                <SelectContent className="bg-[#0F0F11] border-[#222] text-white max-h-80">
                  {autores.map((a) => <SelectItem key={a.id} value={a.id}>{a.name} {a.editora_name ? `· ${a.editora_name}` : ""}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button data-testid="load-autor" onClick={loadAutor} className="h-11 bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm uppercase tracking-wider font-semibold text-xs px-6">
              Gerar relatório
            </Button>
            {reportAutor && (
              <Button data-testid="pdf-autor" onClick={() => downloadPdf("autor", reportAutor.autor.id)} variant="outline" className="h-11 border-[#2a2a2a] rounded-sm hover:border-[#FFD700] hover:text-[#FFD700]">
                <Download className="w-4 h-4 mr-2" /> Baixar PDF Acorde
              </Button>
            )}
          </div>

          {loading && <div className="text-neutral-500">Carregando...</div>}
          {reportAutor && (
            <>
              <AutorReportView data={reportAutor} />
              {isAdmin && (
                <RepasseWidget
                  scope="autor"
                  scopeId={reportAutor.autor.id}
                  competencia={competencia}
                  record={repasses[`autor:${reportAutor.autor.id}:${competencia}`]}
                  defaultValor={reportAutor.totals.liquido}
                  onToggle={toggleRepasse}
                />
              )}
            </>
          )}
        </TabsContent>
      </Tabs>

      {isAdmin && (
        <NotificationsDialog
          open={notifOpen}
          onClose={() => setNotifOpen(false)}
          competencia={competencia}
        />
      )}
    </div>
  );
}

function RepasseWidget({ scope, scopeId, competencia, record, defaultValor, onToggle }) {
  const [valor, setValor] = useState(record?.valor ?? defaultValor ?? 0);
  const [obs, setObs] = useState(record?.observacao || "");

  useEffect(() => {
    setValor(record?.valor ?? defaultValor ?? 0);
    setObs(record?.observacao || "");
  }, [record, defaultValor]);

  const status = record?.status || "pendente";
  const isPaid = status === "pago";

  return (
    <div className="bg-[#0a0a0a] border border-[#1f1f1f] rounded-sm p-6">
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-2">Repasse</div>
          <div className="flex items-center gap-3">
            {isPaid ? (
              <span className="inline-flex items-center gap-2 bg-[#FFD700] text-black px-3 py-1 text-xs uppercase tracking-wider font-bold rounded-sm">
                <CheckCircle2 className="w-4 h-4" /> Pago
              </span>
            ) : (
              <span className="inline-flex items-center gap-2 border border-[#2a2a2a] text-neutral-400 px-3 py-1 text-xs uppercase tracking-wider rounded-sm">
                <Clock className="w-4 h-4" /> Pendente
              </span>
            )}
            {record?.data_pagamento && (
              <span className="text-xs text-neutral-500 mono">
                Pago em {new Date(record.data_pagamento).toLocaleDateString("pt-BR")}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <Label className="text-[10px] uppercase tracking-[0.2em] text-neutral-500 mb-1 block">Valor pago (R$)</Label>
            <Input
              data-testid={`repasse-valor-${scope}`}
              type="number"
              step="0.01"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              className="h-10 w-36 bg-[#0F0F11] border-[#222] rounded-sm mono"
            />
          </div>
          <div>
            <Label className="text-[10px] uppercase tracking-[0.2em] text-neutral-500 mb-1 block">Observação</Label>
            <Input
              data-testid={`repasse-obs-${scope}`}
              value={obs}
              onChange={(e) => setObs(e.target.value)}
              placeholder="Ex: Pix transferido"
              className="h-10 w-64 bg-[#0F0F11] border-[#222] rounded-sm"
            />
          </div>
          <Button
            data-testid={`repasse-toggle-${scope}`}
            onClick={() => onToggle(scope, scopeId, isPaid ? "pendente" : "pago", valor, obs)}
            className={`h-10 rounded-sm uppercase tracking-wider font-semibold text-xs px-5 ${
              isPaid
                ? "bg-transparent border border-[#2a2a2a] text-neutral-300 hover:border-[#FFD700] hover:text-[#FFD700]"
                : "bg-[#FFD700] text-black hover:bg-[#FFE44D]"
            }`}
          >
            {isPaid ? "Marcar como pendente" : "Marcar como pago"}
          </Button>
        </div>
      </div>
      {record?.history?.length > 0 && (
        <div className="mt-6 pt-5 border-t border-[#1a1a1a]">
          <div className="text-[10px] uppercase tracking-[0.3em] text-neutral-500 mb-3">Histórico</div>
          <ul className="space-y-1.5 max-h-40 overflow-auto">
            {record.history.slice().reverse().map((h, i) => (
              <li key={i} className="flex items-center gap-3 text-xs text-neutral-400">
                <span className="mono text-neutral-500">
                  {new Date(h.at).toLocaleString("pt-BR")}
                </span>
                <span className={`px-2 py-0.5 rounded-sm ${h.status === "pago" ? "bg-[#FFD700]/15 text-[#FFD700]" : "border border-[#2a2a2a]"}`}>
                  {h.status}
                </span>
                <span className="mono text-neutral-300">R$ {Number(h.valor || 0).toFixed(2)}</span>
                {h.observacao && <span className="truncate">— {h.observacao}</span>}
                <span className="text-neutral-600 text-[10px] ml-auto">por {h.by}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function NotificationsDialog({ open, onClose, competencia }) {
  const [target, setTarget] = useState("editoras");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  async function send() {
    setSending(true);
    setResult(null);
    try {
      const { data } = await api.post("/notifications/send", {
        competencia,
        target,
      });
      setResult(data);
      toast.success(`${data.sent} e-mails enviados`);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0a0a0a] border-[#1f1f1f] text-white rounded-sm max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Enviar notificações por e-mail</DialogTitle>
          <DialogDescription className="text-xs text-neutral-500">
            Dispara um e-mail com link para o portal da Acorde para cada destinatário com e-mail cadastrado. Competência: <span className="text-white">{competencia || "—"}</span>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-xs uppercase tracking-[0.2em] text-neutral-500 mb-2 block">Enviar para</Label>
            <Select value={target} onValueChange={setTarget}>
              <SelectTrigger data-testid="notif-target" className="bg-[#0F0F11] border-[#222] rounded-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0F0F11] border-[#222] text-white">
                <SelectItem value="editoras">Somente editoras</SelectItem>
                <SelectItem value="autores">Somente autores</SelectItem>
                <SelectItem value="both">Editoras + autores</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs text-neutral-500 leading-relaxed">
            Para enviar, cada editora/autor precisa de um e-mail cadastrado no sistema. O e-mail não contém dados sensíveis — apenas um aviso e link para acessar o portal Acorde.
          </p>
          {result && (
            <div className="border border-[#1f1f1f] rounded-sm p-4 bg-[#0F0F11]">
              <div className="flex gap-6 mono text-sm">
                <div><span className="text-[#FFD700]">Enviados:</span> {result.sent}</div>
                <div><span className="text-neutral-500">Sem e-mail:</span> {result.skipped}</div>
                <div><span className="text-red-400">Erros:</span> {result.errors?.length || 0}</div>
              </div>
              {result.errors?.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-red-400 max-h-24 overflow-auto">
                  {result.errors.slice(0, 10).map((e, i) => (
                    <li key={i}>• {e.editora || e.autor}: {e.error}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
        <DialogFooter className="mt-4">
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Fechar</Button>
          <Button
            data-testid="send-notifications"
            onClick={send}
            disabled={sending || !competencia}
            className="bg-[#FFD700] text-black hover:bg-[#FFE44D] rounded-sm"
          >
            {sending ? "Enviando..." : "Disparar e-mails"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditoraReportView({ data }) {
  const { editora, rows, totals, competencia } = data;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard label="Valor Bruto" value={formatCurrency(totals.bruto)} />
        <SummaryCard label={`Taxa Admin. (${formatPct(editora.admin_fee_percent)})`} value={formatCurrency(totals.taxa)} />
        <SummaryCard label="Valor Líquido" value={formatCurrency(totals.liquido)} accent />
      </div>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-neutral-500">Editora</div>
          <div className="text-2xl font-bold">{editora.name}</div>
          <div className="text-xs text-neutral-500 mono mt-0.5">{editora.cnpj || "—"} · {competencia || "todas as competências"}</div>
        </div>
      </div>
      <div className="border border-[#1f1f1f] rounded-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#0F0F11] text-neutral-500 text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left px-3 py-2.5">Fonte</th>
              <th className="text-left px-3 py-2.5">Obra</th>
              <th className="text-left px-3 py-2.5">Autores</th>
              <th className="text-right px-3 py-2.5">Unid.</th>
              <th className="text-right px-3 py-2.5">Vl. Bruto</th>
              <th className="text-right px-3 py-2.5">Taxa</th>
              <th className="text-right px-3 py-2.5">Vl. Líquido</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="text-center py-10 text-neutral-600">Sem linhas para essa competência.</td></tr>}
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-[#1a1a1a] hover:bg-[#0b0b0b]">
                <td className="px-3 py-2 text-neutral-300">{r.fonte}</td>
                <td className="px-3 py-2 text-white truncate max-w-xs" title={r.obra}>{r.obra}</td>
                <td className="px-3 py-2 text-neutral-400 text-xs truncate max-w-xs" title={r.autores}>{r.autores}</td>
                <td className="px-3 py-2 text-right mono text-neutral-300">{formatNumber(r.unidades)}</td>
                <td className="px-3 py-2 text-right mono text-neutral-300">{formatCurrency(r.vl_editora_bruto)}</td>
                <td className="px-3 py-2 text-right mono text-neutral-500">{formatCurrency(r.taxa_admin_valor)}</td>
                <td className="px-3 py-2 text-right mono text-[#FFD700] font-semibold">{formatCurrency(r.vl_editora_liquido)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AutorReportView({ data }) {
  const { autor, rows, totals, competencia } = data;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard label="Obras" value={formatNumber(totals.obras)} />
        <SummaryCard label="Unidades" value={formatNumber(totals.unidades)} />
        <SummaryCard label="Valor Líquido" value={formatCurrency(totals.liquido)} accent />
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-neutral-500">Autor</div>
        <div className="text-2xl font-bold">{autor.name}</div>
        <div className="text-xs text-neutral-500 mt-0.5">{autor.editora_name || "—"} · {competencia || "todas as competências"}</div>
      </div>
      <div className="border border-[#1f1f1f] rounded-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#0F0F11] text-neutral-500 text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left px-3 py-2.5">Fonte</th>
              <th className="text-left px-3 py-2.5">Formato</th>
              <th className="text-left px-3 py-2.5">Território</th>
              <th className="text-left px-3 py-2.5">Obra</th>
              <th className="text-left px-3 py-2.5">Período</th>
              <th className="text-right px-3 py-2.5">Unid.</th>
              <th className="text-right px-3 py-2.5">Vl. Líquido</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="text-center py-10 text-neutral-600">Sem linhas para essa competência.</td></tr>}
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-[#1a1a1a] hover:bg-[#0b0b0b]">
                <td className="px-3 py-2 text-neutral-300">{r.fonte}</td>
                <td className="px-3 py-2 text-neutral-400 text-xs">{r.formato}</td>
                <td className="px-3 py-2 text-neutral-400">{r.territorio}</td>
                <td className="px-3 py-2 text-white truncate max-w-xs" title={r.obra}>{r.obra}</td>
                <td className="px-3 py-2 text-neutral-500 text-xs">{r.periodo}</td>
                <td className="px-3 py-2 text-right mono text-neutral-300">{formatNumber(r.unidades)}</td>
                <td className="px-3 py-2 text-right mono text-[#FFD700] font-semibold">{formatCurrency(r.vl_liquido)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, accent }) {
  return (
    <div className={`border rounded-sm p-5 ${accent ? "bg-[#FFD700] border-[#FFD700] text-black" : "bg-[#0a0a0a] border-[#1f1f1f] text-white"}`}>
      <div className={`text-[10px] uppercase tracking-[0.25em] ${accent ? "text-black/70" : "text-neutral-500"}`}>{label}</div>
      <div className="mono text-2xl font-bold mt-2">{value}</div>
    </div>
  );
}
