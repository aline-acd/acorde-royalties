import { useEffect, useState } from "react";
import { api, formatCurrency, formatNumber } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from "recharts";

const COLORS = ["#FFD700", "#ffffff", "#C8A615", "#888888", "#555555"];

export default function Dashboard() {
  const { user } = useAuth();
  const [competencias, setCompetencias] = useState([]);
  const [competencia, setCompetencia] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/competencias").then((r) => {
      setCompetencias(r.data || []);
      if ((r.data || []).length > 0) setCompetencia(r.data[0]);
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    api.get("/dashboard/summary", { params: competencia ? { competencia } : {} })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [competencia]);

  const t = data?.totals || {};

  return (
    <div className="space-y-10">
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="stagger-up">
          <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-2">Dashboard</div>
          <h1 className="text-5xl font-extrabold leading-none">Olá, {user?.name || "parceira"}.</h1>
          <p className="text-neutral-500 mt-3 text-sm max-w-xl">
            {user?.role === "admin"
              ? "Visão geral da operação Acorde. Consolidação dos relatórios Abramus Digital por competência."
              : "Resumo das suas obras e repasses na Acorde para a competência selecionada."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs uppercase tracking-[0.2em] text-neutral-500">Competência</div>
          <Select value={competencia || "__all__"} onValueChange={(v) => setCompetencia(v === "__all__" ? "" : v)}>
            <SelectTrigger
              data-testid="dash-competencia"
              className="w-64 h-11 bg-[#0F0F11] border-[#222] rounded-sm text-white focus:ring-1 focus:ring-[#FFD700] focus:border-[#FFD700]"
            >
              <SelectValue placeholder="Todas as competências" />
            </SelectTrigger>
            <SelectContent className="bg-[#0F0F11] border-[#222] text-white">
              <SelectItem value="__all__">Todas as competências</SelectItem>
              {competencias.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi
          label="Valor total (Geral)"
          value={formatCurrency(t.valor_total_geral)}
          hint={`${formatNumber(t.linhas_geral)} linhas`}
          accent
          testid="kpi-total-geral"
        />
        <Kpi
          label="Valor Editora (bruto)"
          value={formatCurrency(t.valor_total_editora)}
          hint={`${formatNumber(t.linhas_editora)} linhas`}
          testid="kpi-total-editora"
        />
        <Kpi
          label="Valor Autor (bruto)"
          value={formatCurrency(t.valor_total_autor)}
          hint={`${formatNumber(t.linhas_autor)} linhas`}
          testid="kpi-total-autor"
        />
        <Kpi
          label={user?.role === "admin" ? "Editoras cadastradas" : "Autores vinculados"}
          value={user?.role === "admin" ? formatNumber(t.editoras_cadastradas) : formatNumber(t.autores_cadastrados)}
          hint={user?.role === "admin" ? `${formatNumber(t.autores_cadastrados)} autores` : ""}
          testid="kpi-count"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <Card className="col-span-1 lg:col-span-8 bg-[#0a0a0a] border border-[#1f1f1f] rounded-sm p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-xl font-bold">Receita por fonte</h3>
              <p className="text-xs text-neutral-500 mt-1">Soma do VL_AUTOR por plataforma (SPOTIFY, YOUTUBE, AMAZON...)</p>
            </div>
          </div>
          <div className="h-72 min-h-[280px]">
            {loading ? (
              <div className="flex items-center justify-center h-full text-neutral-500 text-sm">Carregando...</div>
            ) : (data?.por_fonte || []).length === 0 ? (
              <div className="flex items-center justify-center h-full text-neutral-600 text-sm">
                Sem dados. Faça upload do relatório de autores em "Uploads Abramus".
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.por_fonte} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" vertical={false} />
                  <XAxis dataKey="fonte" tick={{ fill: "#888", fontSize: 11 }} stroke="#333" />
                  <YAxis tick={{ fill: "#888", fontSize: 11 }} stroke="#333" tickFormatter={(v) => `R$${Math.round(v)}`} />
                  <Tooltip
                    contentStyle={{ background: "#0F0F11", border: "1px solid #222", borderRadius: 2, color: "#fff" }}
                    formatter={(v) => formatCurrency(v)}
                  />
                  <Bar dataKey="total" radius={[2, 2, 0, 0]}>
                    {data.por_fonte.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card className="col-span-1 lg:col-span-4 bg-[#0a0a0a] border border-[#1f1f1f] rounded-sm p-6">
          <h3 className="text-xl font-bold">{user?.role === "admin" ? "Top editoras" : "Resumo"}</h3>
          <p className="text-xs text-neutral-500 mt-1 mb-4">
            {user?.role === "admin" ? "Por volume bruto do mês" : "Totais do período"}
          </p>
          {user?.role === "admin" ? (
            <ul className="space-y-3">
              {(data?.top_editoras || []).slice(0, 8).map((e, i) => (
                <li key={i} className="flex items-center justify-between border-b border-[#1a1a1a] pb-2">
                  <span className="text-sm text-white truncate pr-2" title={e.titular}>{e.titular}</span>
                  <span className="mono text-sm text-[#FFD700]">{formatCurrency(e.total)}</span>
                </li>
              ))}
              {(data?.top_editoras || []).length === 0 && (
                <li className="text-neutral-600 text-sm">Nenhum relatório editora processado.</li>
              )}
            </ul>
          ) : (
            <div className="space-y-4">
              <SummaryRow label="Valor Autor bruto" value={formatCurrency(t.valor_total_autor)} />
              <SummaryRow label="Linhas processadas" value={formatNumber(t.linhas_autor)} />
              <SummaryRow label="Competência" value={competencia || "—"} />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value, hint, accent = false, testid }) {
  return (
    <div
      data-testid={testid}
      className={`stagger-up border rounded-sm p-6 ${
        accent ? "bg-[#FFD700] text-black border-[#FFD700]" : "bg-[#0a0a0a] border-[#1f1f1f] text-white"
      }`}
    >
      <div className={`text-[10px] uppercase tracking-[0.25em] ${accent ? "text-black/70" : "text-neutral-500"}`}>
        {label}
      </div>
      <div className={`mono text-3xl font-bold mt-3 ${accent ? "text-black" : "text-white"}`}>{value}</div>
      {hint && (
        <div className={`text-xs mt-1 ${accent ? "text-black/60" : "text-neutral-600"}`}>{hint}</div>
      )}
    </div>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-[#1a1a1a] pb-2">
      <span className="text-xs uppercase tracking-wider text-neutral-500">{label}</span>
      <span className="mono text-sm text-white">{value}</span>
    </div>
  );
}
