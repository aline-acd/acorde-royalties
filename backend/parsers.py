"""Parsers for the three Abramus Digital report types.

- Relatório Geral: CSV (sometimes shipped inside a ZIP, one file per editora).
  Delimiter: comma. Decimal: comma (Brazilian). Columns include:
    Competência, Período, Cliente, Editora, Território, Fonte, Formato,
    Pagamento, Id Obra, ISWC, Título da Obra, Autores, Interprete, ISRC,
    Unidades, % Controle, Val. Liquido

- Relatório Editora: XLSX with columns:
    PERIODO, CLIENTE, TITULAR, NOME, CAT, ID_OBRA, OBRA, FONTE, PAGAMENTO,
    AUTORES, UNIDADES, PERC_TOTAL, PERC_RECEBIDO, LIQUIDO, PERC_EDITORA,
    VL_EDITORA, ADMINISTRACAO_CLIENTE, VL_TAXA

- Relatório Autor: XLSX with columns:
    COMPETENCIA, CLIENTE, TITULAR, NOME, ID_OBRA, OBRA, TIPO_UTILIZACAO,
    TERRITORIO, FONTE, FORMATO, PERIODO, AUTORES, UNIDADES, PERC_TOTAL,
    PERC_RECEBIDO, LIQUIDO, PERC_AUTOR, VL_AUTOR, VL_EDITORA
"""
import io
import math
import zipfile
import pandas as pd
import unicodedata


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().upper()
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    return " ".join(s.split())


def _to_float_br(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return 0.0
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    # Brazilian decimal: "1.234,56" -> "1234.56"
    s = s.replace(".", "").replace(",", ".") if "," in s else s
    try:
        return float(s)
    except Exception:
        return 0.0


def _clean_value(v):
    """Return a JSON/Mongo friendly value (no NaN, no numpy types)."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return None
        return float(v)
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return str(v)
    if isinstance(v, (int, str, bool)):
        return v
    return str(v)


def parse_general_csv(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse one Relatório Geral CSV file.
    Returns a list of normalized dict rows."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")
    df = pd.read_csv(io.StringIO(text), sep=",", dtype=str, keep_default_na=False)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "competencia": r.get("Competência", ""),
                "periodo": r.get("Período", ""),
                "cliente": r.get("Cliente", ""),
                "editora_nome": r.get("Editora", ""),
                "editora_norm": _norm(r.get("Editora", "")),
                "territorio": r.get("Território", ""),
                "fonte": r.get("Fonte", ""),
                "formato": r.get("Formato", ""),
                "pagamento": r.get("Pagamento", ""),
                "id_obra": r.get("Id Obra", ""),
                "iswc": r.get("ISWC", ""),
                "titulo_obra": r.get("Título da Obra", ""),
                "autores": r.get("Autores", ""),
                "interprete": r.get("Interprete", ""),
                "isrc": r.get("ISRC", ""),
                "unidades": int(_to_float_br(r.get("Unidades", 0))),
                "perc_controle": _to_float_br(r.get("% Controle", 0)),
                "val_liquido": _to_float_br(r.get("Val. Liquido", 0)),
                "source_file": filename,
            }
        )
    return rows


def parse_general_zip_or_csv(file_bytes: bytes, filename: str) -> list[dict]:
    """Handle either a single CSV or a ZIP of CSVs."""
    all_rows = []
    if filename.lower().endswith(".zip") or file_bytes[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(file_bytes))
        for name in zf.namelist():
            if name.endswith("/") or not name.lower().endswith(".csv"):
                continue
            with zf.open(name) as fh:
                data = fh.read()
            all_rows.extend(parse_general_csv(data, name))
    else:
        all_rows.extend(parse_general_csv(file_bytes, filename))
    return all_rows


def parse_editora_xlsx(file_bytes: bytes, filename: str) -> list[dict]:
    df = pd.read_excel(io.BytesIO(file_bytes), dtype=object)
    rows = []
    for _, r in df.iterrows():
        titular = r.get("TITULAR", "")
        nome = r.get("NOME", "")
        rows.append(
            {
                "periodo": _clean_value(r.get("PERIODO")),
                "cliente": _clean_value(r.get("CLIENTE")),
                "titular": _clean_value(titular),
                "titular_norm": _norm(titular),
                "nome": _clean_value(nome),
                "nome_norm": _norm(nome),
                "cat": _clean_value(r.get("CAT")),
                "id_obra": _clean_value(r.get("ID_OBRA")),
                "obra": _clean_value(r.get("OBRA")),
                "fonte": _clean_value(r.get("FONTE")),
                "pagamento": _clean_value(r.get("PAGAMENTO")),
                "autores": _clean_value(r.get("AUTORES")),
                "unidades": int(_to_float_br(r.get("UNIDADES", 0))),
                "perc_total": _to_float_br(r.get("PERC_TOTAL", 0)),
                "perc_recebido": _to_float_br(r.get("PERC_RECEBIDO", 0)),
                "liquido": _to_float_br(r.get("LIQUIDO", 0)),
                "perc_editora": _to_float_br(r.get("PERC_EDITORA", 0)),
                "vl_editora": _to_float_br(r.get("VL_EDITORA", 0)),
                "administracao_cliente": _clean_value(r.get("ADMINISTRACAO_CLIENTE")),
                "vl_taxa": _to_float_br(r.get("VL_TAXA", 0)),
                "source_file": filename,
            }
        )
    return rows


def parse_autor_xlsx(file_bytes: bytes, filename: str) -> list[dict]:
    df = pd.read_excel(io.BytesIO(file_bytes), dtype=object)
    rows = []
    for _, r in df.iterrows():
        titular = r.get("TITULAR", "")
        nome = r.get("NOME", "")
        rows.append(
            {
                "competencia": _clean_value(r.get("COMPETENCIA")),
                "cliente": _clean_value(r.get("CLIENTE")),
                "titular": _clean_value(titular),
                "titular_norm": _norm(titular),
                "nome": _clean_value(nome),
                "nome_norm": _norm(nome),
                "id_obra": _clean_value(r.get("ID_OBRA")),
                "obra": _clean_value(r.get("OBRA")),
                "tipo_utilizacao": _clean_value(r.get("TIPO_UTILIZACAO")),
                "territorio": _clean_value(r.get("TERRITORIO")),
                "fonte": _clean_value(r.get("FONTE")),
                "formato": _clean_value(r.get("FORMATO")),
                "periodo": _clean_value(r.get("PERIODO")),
                "autores": _clean_value(r.get("AUTORES")),
                "unidades": int(_to_float_br(r.get("UNIDADES", 0))),
                "perc_total": _to_float_br(r.get("PERC_TOTAL", 0)),
                "perc_recebido": _to_float_br(r.get("PERC_RECEBIDO", 0)),
                "liquido": _to_float_br(r.get("LIQUIDO", 0)),
                "perc_autor": _to_float_br(r.get("PERC_AUTOR", 0)),
                "vl_autor": _to_float_br(r.get("VL_AUTOR", 0)),
                "vl_editora": _to_float_br(r.get("VL_EDITORA", 0)),
                "source_file": filename,
            }
        )
    return rows


def parse_bulk_fees_csv(file_bytes: bytes) -> list[dict]:
    """Parse a CSV with columns: nome,taxa_admin (percent 0-100). Optional column: editora (for autores)."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")
    sep = "," if text.count(",") >= text.count(";") else ";"
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [c.strip().lower() for c in df.columns]
    out = []
    for _, r in df.iterrows():
        out.append(
            {
                "nome": (r.get("nome") or r.get("name") or "").strip(),
                "taxa_admin": _to_float_br(r.get("taxa_admin") or r.get("taxa") or r.get("fee") or 0),
                "editora": (r.get("editora") or "").strip(),
                "cnpj": (r.get("cnpj") or "").strip(),
                "email": (r.get("email") or "").strip(),
            }
        )
    return out
