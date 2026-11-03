#!/usr/bin/env python3
"""Importa planilhas Abramus (aba 'Todos') e gera lançamentos normalizados.

Uso:
    python scripts/import_abramus.py <pasta_com_xlsx> <pasta_saida_FORA_do_repo>

ATENÇÃO: a saída contém dados reais de clientes. Nunca grave dentro do repositório
nem em pastas sincronizadas (Google Drive).
"""
import glob
import os
import re
import sys

import pandas as pd

MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "MARÇO": 3, "ABRIL": 4, "MAIO": 5,
         "JUNHO": 6, "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10,
         "NOVEMBRO": 11, "DEZEMBRO": 12}

# Colunas esperadas por tipo (contrato do layout Abramus). Divergência = rejeição.
COLUNAS = {
    "EDITORA": ["PERIODO", "CLIENTE", "TITULAR", "NOME", "CAT", "ID_OBRA", "OBRA", "FONTE",
                "PAGAMENTO", "AUTORES", "UNIDADES", "PERC_TOTAL", "PERC_RECEBIDO", "LIQUIDO",
                "PERC_EDITORA", "VL_EDITORA", "ADMINISTRACAO_CLIENTE", "VL_TAXA"],
    "AUTOR": ["COMPETENCIA", "CLIENTE", "TITULAR", "NOME", "ID_OBRA", "OBRA", "TIPO_UTILIZACAO",
              "TERRITORIO", "FONTE", "FORMATO", "PERIODO", "AUTORES", "UNIDADES", "PERC_TOTAL",
              "PERC_RECEBIDO", "LIQUIDO", "PERC_AUTOR", "VL_AUTOR", "VL_EDITORA"],
}


def competencia(texto):
    """'2026 - JULHO' -> date(2026, 7, 1). Retorna None se não reconhecer."""
    m = re.match(r"\s*(\d{4})\s*-\s*([A-ZÇÃ]+)", str(texto).upper())
    if not m or m.group(2) not in MESES:
        return None
    return pd.Timestamp(int(m.group(1)), MESES[m.group(2)], 1).date()


def numero(serie):
    return pd.to_numeric(serie, errors="coerce").fillna(0.0)


def ler_arquivo(caminho):
    nome = os.path.basename(caminho).upper()
    tipo = "EDITORA" if "EDITORES" in nome else "AUTOR" if "AUTORES" in nome else None
    if tipo is None:
        return None, None, "Nome de arquivo não identifica Editora nem Autor"
    df = pd.read_excel(caminho, sheet_name="Todos", dtype=str)
    faltando = [c for c in COLUNAS[tipo] if c not in df.columns]
    if faltando:
        return tipo, None, f"Colunas ausentes: {', '.join(faltando)}"
    return tipo, df, None


def normalizar(tipo, df):
    if tipo == "EDITORA":
        out = pd.DataFrame({
            "competencia_txt": df["PERIODO"], "editora": df["TITULAR"].str.strip(),
            "beneficiario": df["NOME"].str.strip(), "categoria": df["CAT"],
            "id_obra": df["ID_OBRA"], "obra": df["OBRA"], "fonte": df["FONTE"],
            "regiao": None, "formato": None, "tipo_utilizacao": None,
            "pagamento": df["PAGAMENTO"], "periodo_texto": None,
            "unidades": numero(df["UNIDADES"]), "perc_total": numero(df["PERC_TOTAL"]),
            "perc_recebido": numero(df["PERC_RECEBIDO"]), "liquido": numero(df["LIQUIDO"]),
            "perc_beneficiario": numero(df["PERC_EDITORA"]),
            "valor_bruto": numero(df["VL_EDITORA"]),
        })
    else:
        out = pd.DataFrame({
            "competencia_txt": df["COMPETENCIA"], "editora": df["TITULAR"].str.strip(),
            "beneficiario": df["NOME"].str.strip(), "categoria": None,
            "id_obra": df["ID_OBRA"], "obra": df["OBRA"], "fonte": df["FONTE"],
            "regiao": df["TERRITORIO"], "formato": df["FORMATO"],
            "tipo_utilizacao": df["TIPO_UTILIZACAO"], "pagamento": None,
            "periodo_texto": df["PERIODO"],
            "unidades": numero(df["UNIDADES"]), "perc_total": numero(df["PERC_TOTAL"]),
            "perc_recebido": numero(df["PERC_RECEBIDO"]), "liquido": numero(df["LIQUIDO"]),
            "perc_beneficiario": numero(df["PERC_AUTOR"]),
            "valor_bruto": numero(df["VL_AUTOR"]),
        })
    out["competencia"] = out["competencia_txt"].map(competencia)
    out["tipo_arquivo"] = tipo
    return out


def main(src, saida):
    os.makedirs(saida, exist_ok=True)
    relatorio = []
    for arq in sorted(glob.glob(os.path.join(src, "*.xlsx"))):
        tipo, df, erro = ler_arquivo(arq)
        nome = os.path.basename(arq)
        if erro:
            relatorio.append((nome, "REJEITADO", erro, 0))
            continue
        lanc = normalizar(tipo, df)
        comps = sorted({c for c in lanc["competencia"] if c is not None})
        sem_comp = int(lanc["competencia"].isna().sum())
        if sem_comp:
            relatorio.append((nome, "REVISAR", f"{sem_comp} linhas sem competência reconhecida", len(lanc)))
        if len(comps) > 1:
            status, motivo = "CONFLITO", f"Competências diferentes no mesmo arquivo: {comps}"
        elif not comps:
            status, motivo = "REJEITADO", "Nenhuma competência reconhecida"
        else:
            status, motivo = "RASCUNHO", f"Competência {comps[0]}"
        lanc["upload_arquivo"] = nome
        lanc["status_lote"] = status
        lanc.to_csv(os.path.join(saida, nome.replace(".xlsx", ".lancamentos.csv")),
                    sep=";", index=False, encoding="utf-8-sig")
        relatorio.append((nome, status, motivo, len(lanc)))

    with open(os.path.join(saida, "relatorio_importacao.txt"), "w", encoding="utf-8") as fh:
        for nome, status, motivo, linhas in relatorio:
            fh.write(f"{status:<10} {linhas:>6} linhas  {nome}  -- {motivo}\n")
    for nome, status, motivo, linhas in relatorio:
        print(f"{status:<10} {linhas:>6} linhas  {nome}  -- {motivo}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
