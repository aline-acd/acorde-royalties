import { useEffect, useState } from "react";
import { api, API, formatCurrency, formatNumber, formatPct, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Download, FileText } from "lucide-react";

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

  useEffect(() => {
    api.get("/competencias").then((r) => setCompetencias(r.data || []));
    api.get("/editoras").then((r) => {
      setEditoras(r.data || []);
      if (!isAdmin && r.data?.[0]) setSelectedEditora(r.data[0].id);
    });
    api.get("/autores").then((r) => setAutores(r.data || []));
  }, []);

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

  return (
    <div className="space-y-10">
      <div>
        <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-2">Relatórios Acorde</div>
        <h1 className="text-5xl font-extrabold leading-none">Visualize & exporte</h1>
        <p className="text-neutral-500 mt-3 text-sm max-w-2xl">
          Gere relatórios Acorde individuais a partir dos dados Abramus processados. Exporte em PDF modelo Acorde.
        </p>
      </div>

      <div className="flex items-center gap-3">
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
          {reportEditora && <EditoraReportView data={reportEditora} />}
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
          {reportAutor && <AutorReportView data={reportAutor} />}
        </TabsContent>
      </Tabs>
    </div>
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
