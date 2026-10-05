import { useEffect, useState, useRef } from "react";
import { api, formatApiError, formatNumber } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Trash2, UploadCloud, FileSpreadsheet, Archive } from "lucide-react";

const TYPES = [
  {
    key: "geral",
    title: "Relatório Geral",
    hint: "Envie o ZIP exportado pela Abramus (com um CSV por editora) ou um único CSV geral.",
    icon: Archive,
    accept: ".zip,.csv",
  },
  {
    key: "editora",
    title: "Relatório Editora",
    hint: "Arquivo XLSX com as colunas PERIODO, CLIENTE, TITULAR, VL_EDITORA, PERC_EDITORA...",
    icon: FileSpreadsheet,
    accept: ".xlsx,.xls",
  },
  {
    key: "autor",
    title: "Relatório Autor",
    hint: "Arquivo XLSX com as colunas COMPETENCIA, TITULAR, NOME, VL_AUTOR, PERC_AUTOR...",
    icon: FileSpreadsheet,
    accept: ".xlsx,.xls",
  },
];

export default function Uploads() {
  const [uploads, setUploads] = useState([]);
  const [busy, setBusy] = useState(null);

  async function refresh() {
    const { data } = await api.get("/uploads");
    setUploads(data || []);
  }

  useEffect(() => { refresh(); }, []);

  async function handleUpload(type, file) {
    if (!file) return;
    setBusy(type);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post(`/uploads/${type}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${data.rows.toLocaleString("pt-BR")} linhas importadas (${data.competencia || "sem competência"})`);
      refresh();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(null);
    }
  }

  async function removeUpload(id) {
    if (!window.confirm("Remover este upload e todas as linhas associadas?")) return;
    try {
      await api.delete(`/uploads/${id}`);
      toast.success("Upload removido");
      refresh();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  }

  return (
    <div className="space-y-10">
      <div>
        <div className="text-xs uppercase tracking-[0.3em] text-[#FFD700] mb-2">Uploads Abramus</div>
        <h1 className="text-5xl font-extrabold leading-none">Processamento de relatórios</h1>
        <p className="text-neutral-500 mt-3 text-sm max-w-2xl">
          Envie os três tipos de relatório da Abramus Digital. O sistema converte, normaliza e
          consolida tudo para que você possa gerar os relatórios Acorde por editora e por autor.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {TYPES.map((t) => (
          <UploadCard key={t.key} type={t} busy={busy === t.key} onFile={(f) => handleUpload(t.key, f)} />
        ))}
      </div>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Histórico de uploads</h2>
          <div className="text-xs text-neutral-500">{formatNumber(uploads.length)} registros</div>
        </div>
        <div className="border border-[#1f1f1f] rounded-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#0F0F11] text-neutral-500 text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-3">Arquivo</th>
                <th className="text-left px-4 py-3">Tipo</th>
                <th className="text-left px-4 py-3">Competência</th>
                <th className="text-right px-4 py-3">Linhas</th>
                <th className="text-left px-4 py-3">Data</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {uploads.length === 0 && (
                <tr><td colSpan={6} className="text-center text-neutral-600 py-10">Nenhum upload ainda.</td></tr>
              )}
              {uploads.map((u) => (
                <tr key={u.id} className="border-t border-[#1a1a1a] hover:bg-[#0b0b0b]">
                  <td className="px-4 py-3 text-white truncate max-w-xs" title={u.filename}>{u.filename}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex px-2 py-0.5 text-[10px] uppercase tracking-wider border border-[#FFD700] text-[#FFD700] rounded-sm">
                      {u.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-neutral-400">{u.competencia || "—"}</td>
                  <td className="px-4 py-3 text-right mono text-white">{formatNumber(u.rows_count)}</td>
                  <td className="px-4 py-3 text-neutral-500 mono text-xs">
                    {new Date(u.uploaded_at).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      data-testid={`delete-upload-${u.id}`}
                      onClick={() => removeUpload(u.id)}
                      className="text-neutral-500 hover:text-red-400"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function UploadCard({ type, busy, onFile }) {
  const ref = useRef(null);
  const [drag, setDrag] = useState(false);

  return (
    <div className="bg-[#0a0a0a] border border-[#1f1f1f] rounded-sm p-6 flex flex-col">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold">{type.title}</h3>
          <p className="text-xs text-neutral-500 mt-1">{type.hint}</p>
        </div>
        <type.icon className="w-5 h-5 text-[#FFD700]" />
      </div>

      <div
        className={`dropzone mt-6 flex-1 min-h-[160px] flex flex-col items-center justify-center rounded-sm p-6 cursor-pointer text-center ${drag ? "active" : ""}`}
        onClick={() => ref.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files?.[0]) onFile(e.dataTransfer.files[0]);
        }}
        data-testid={`dropzone-${type.key}`}
      >
        <UploadCloud className="w-7 h-7 text-neutral-500 mb-3" />
        <div className="text-sm text-white">
          {busy ? "Processando..." : <>Arraste o arquivo ou <span className="text-[#FFD700] underline">selecione</span></>}
        </div>
        <div className="text-[11px] text-neutral-600 mt-1">Aceita: {type.accept}</div>
        <input
          ref={ref}
          type="file"
          accept={type.accept}
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0])}
          data-testid={`file-${type.key}`}
        />
      </div>
    </div>
  );
}
