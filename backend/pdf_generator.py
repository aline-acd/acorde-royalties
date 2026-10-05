"""Acorde-branded PDF generators for Editora and Autor reports.

Design: Black header + yellow accent bar + white body. Simple, dense tables,
tabular numeric data.
"""
import io
import os
from pathlib import Path
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER


_CELL_STYLE = None
_CELL_STYLE_RIGHT = None


def _cell_style():
    global _CELL_STYLE
    if _CELL_STYLE is None:
        _CELL_STYLE = ParagraphStyle(
            name="Cell",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=ACORDE_BLACK,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
    return _CELL_STYLE


def _cell_style_right():
    global _CELL_STYLE_RIGHT
    if _CELL_STYLE_RIGHT is None:
        _CELL_STYLE_RIGHT = ParagraphStyle(
            name="CellRight",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=ACORDE_BLACK,
            alignment=TA_RIGHT,
            wordWrap="CJK",
        )
    return _CELL_STYLE_RIGHT


def _p(text, right=False):
    """Wrap value as Paragraph so it word-wraps inside the cell."""
    if text is None:
        text = ""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, _cell_style_right() if right else _cell_style())


ACORDE_BLACK = colors.HexColor("#000000")
ACORDE_SURFACE = colors.HexColor("#070707")
ACORDE_YELLOW = colors.HexColor("#FFD700")
ACORDE_WHITE = colors.HexColor("#FFFFFF")
ACORDE_GREY = colors.HexColor("#DDDDDD")
ACORDE_MUTED = colors.HexColor("#666666")

_LOGO_PATH = Path(__file__).parent / "assets" / "acorde_logo_transparent.png"
_LOGO = None


def _logo():
    global _LOGO
    if _LOGO is None and _LOGO_PATH.exists():
        _LOGO = ImageReader(str(_LOGO_PATH))
    return _LOGO


def _money(v) -> str:
    try:
        v = float(v)
    except Exception:
        v = 0.0
    s = f"{v:,.2f}"
    # BR format: thousands "." decimal ","
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _pct(v) -> str:
    try:
        v = float(v)
    except Exception:
        v = 0.0
    return f"{v:.2f}%".replace(".", ",")


def _header_footer(canvas, doc, title: str, subtitle: str):
    width, height = doc.pagesize
    canvas.saveState()
    # Black header band (deeper so logo breathes)
    header_h = 26 * mm
    canvas.setFillColor(ACORDE_BLACK)
    canvas.rect(0, height - header_h, width, header_h, fill=1, stroke=0)
    # Yellow accent bar
    canvas.setFillColor(ACORDE_YELLOW)
    canvas.rect(0, height - header_h - 2 * mm, width, 2 * mm, fill=1, stroke=0)
    # Logo (centered vertically in header band)
    logo = _logo()
    if logo is not None:
        try:
            canvas.drawImage(
                logo,
                12 * mm,
                height - header_h + 3 * mm,
                width=48 * mm,
                height=20 * mm,
                mask="auto",
                preserveAspectRatio=True,
            )
        except Exception:
            canvas.setFillColor(ACORDE_YELLOW)
            canvas.setFont("Helvetica-Bold", 20)
            canvas.drawString(15 * mm, height - 15 * mm, "ACORDE")
    else:
        canvas.setFillColor(ACORDE_YELLOW)
        canvas.setFont("Helvetica-Bold", 20)
        canvas.drawString(15 * mm, height - 15 * mm, "ACORDE")
    # Title right
    canvas.setFillColor(ACORDE_WHITE)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawRightString(width - 15 * mm, height - 12 * mm, title)
    canvas.setFillColor(ACORDE_YELLOW)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 15 * mm, height - 18 * mm, subtitle)
    # Footer
    canvas.setFillColor(ACORDE_BLACK)
    canvas.rect(0, 0, width, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(ACORDE_YELLOW)
    canvas.rect(0, 10 * mm, width, 1 * mm, fill=1, stroke=0)
    canvas.setFillColor(ACORDE_WHITE)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        15 * mm,
        4 * mm,
        f"Emitido em {datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')} • Acorde Music Rights • Compondo Negócios",
    )
    canvas.drawRightString(width - 15 * mm, 4 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AcordeH1",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=ACORDE_BLACK,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AcordeH2",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=ACORDE_BLACK,
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AcordeBody",
            fontName="Helvetica",
            fontSize=9,
            textColor=ACORDE_BLACK,
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AcordeMuted",
            fontName="Helvetica",
            fontSize=8,
            textColor=ACORDE_MUTED,
        )
    )
    return styles


def _summary_table(data_rows):
    """data_rows: list of (label, value) tuples."""
    tbl = Table(data_rows, colWidths=[55 * mm, 45 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), ACORDE_BLACK),
                ("TEXTCOLOR", (0, 0), (0, -1), ACORDE_YELLOW),
                ("TEXTCOLOR", (1, 0), (1, -1), ACORDE_BLACK),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, ACORDE_GREY),
                ("BOX", (0, 0), (-1, -1), 0.5, ACORDE_BLACK),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return tbl


def _detail_table(headers, rows, col_widths):
    data = [headers] + rows
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), ACORDE_BLACK),
        ("TEXTCOLOR", (0, 0), (-1, 0), ACORDE_YELLOW),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.25, ACORDE_GREY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ACORDE_WHITE, colors.HexColor("#F7F7F7")]),
        ("TEXTCOLOR", (0, 1), (-1, -1), ACORDE_BLACK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    tbl.setStyle(TableStyle(style))
    return tbl


def generate_editora_pdf(
    editora_name: str,
    cnpj: str,
    competencia: str,
    admin_fee_percent: float,
    rows: list[dict],
    totals: dict,
) -> bytes:
    """rows items should contain: fonte, obra, autores, unidades, vl_editora_bruto,
    taxa_admin_valor, vl_editora_liquido."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        topMargin=35 * mm,
        bottomMargin=15 * mm,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
    )
    styles = _styles()
    story = []

    title = f"RELATÓRIO EDITORA"
    subtitle = f"{editora_name}"
    story.append(Paragraph(f"<b>Relatório Analítico • Editora</b>", styles["AcordeH1"]))
    story.append(Paragraph(f"{editora_name}", styles["AcordeBody"]))
    if cnpj:
        story.append(Paragraph(f"CNPJ: {cnpj}", styles["AcordeMuted"]))
    story.append(Paragraph(f"Competência: <b>{competencia or '—'}</b>", styles["AcordeMuted"]))
    story.append(Spacer(1, 8))

    summary = [
        ["VALOR BRUTO EDITORA", _money(totals.get("bruto", 0))],
        [f"TAXA ADMINISTRAÇÃO ({_pct(admin_fee_percent)})", _money(totals.get("taxa", 0))],
        ["VALOR LÍQUIDO A REPASSAR", _money(totals.get("liquido", 0))],
    ]
    story.append(_summary_table(summary))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Detalhamento por obra", styles["AcordeH2"]))

    headers = [
        "Fonte",
        "Obra",
        "Autores",
        "Unid.",
        "% Editora",
        "Vl. Bruto",
        "Taxa Admin.",
        "Vl. Líquido",
    ]
    body = []
    for r in rows:
        body.append(
            [
                _p(r.get("fonte", "")),
                _p(r.get("obra", "")),
                _p(r.get("autores", "")),
                f"{int(r.get('unidades', 0)):,}".replace(",", "."),
                _pct(float(r.get("perc_editora", 0)) * 100 if float(r.get("perc_editora", 0)) <= 1 else float(r.get("perc_editora", 0))),
                _money(r.get("vl_editora_bruto", 0)),
                _money(r.get("taxa_admin_valor", 0)),
                _money(r.get("vl_editora_liquido", 0)),
            ]
        )
    body.append(
        [
            "",
            "",
            "TOTAIS",
            "",
            "",
            _money(totals.get("bruto", 0)),
            _money(totals.get("taxa", 0)),
            _money(totals.get("liquido", 0)),
        ]
    )
    col_widths = [30 * mm, 55 * mm, 65 * mm, 15 * mm, 18 * mm, 24 * mm, 24 * mm, 25 * mm]
    tbl = _detail_table(headers, body, col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, -1), (-1, -1), ACORDE_BLACK),
                ("TEXTCOLOR", (0, -1), (-1, -1), ACORDE_YELLOW),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(tbl)

    def _on_page(canvas, d):
        _header_footer(canvas, d, title, subtitle)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def generate_autor_pdf(
    autor_name: str,
    editora_name: str,
    competencia: str,
    rows: list[dict],
    totals: dict,
) -> bytes:
    """Autor PDF: NO admin tax column — only final liquid value per row/total."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        topMargin=35 * mm,
        bottomMargin=15 * mm,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
    )
    styles = _styles()
    story = []

    title = "RELATÓRIO AUTOR"
    subtitle = autor_name
    story.append(Paragraph("<b>Relatório Analítico • Autor</b>", styles["AcordeH1"]))
    story.append(Paragraph(f"Autor: {autor_name}", styles["AcordeBody"]))
    story.append(Paragraph(f"Editora: {editora_name}", styles["AcordeMuted"]))
    story.append(Paragraph(f"Competência: <b>{competencia or '—'}</b>", styles["AcordeMuted"]))
    story.append(Spacer(1, 8))

    summary = [
        ["TOTAL DE OBRAS", str(totals.get("obras", 0))],
        ["TOTAL DE UNIDADES", f"{int(totals.get('unidades', 0)):,}".replace(",", ".")],
        ["VALOR LÍQUIDO A RECEBER", _money(totals.get("liquido", 0))],
    ]
    story.append(_summary_table(summary))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Detalhamento por obra", styles["AcordeH2"]))

    headers = [
        "Fonte",
        "Formato",
        "Território",
        "Obra",
        "Período",
        "Unid.",
        "% Autor",
        "Valor Líquido",
    ]
    body = []
    for r in rows:
        body.append(
            [
                _p(r.get("fonte", "")),
                _p(r.get("formato", "")),
                _p(r.get("territorio", "")),
                _p(r.get("obra", "")),
                _p(r.get("periodo", "")),
                f"{int(r.get('unidades', 0)):,}".replace(",", "."),
                _pct(float(r.get("perc_autor", 0)) * 100 if float(r.get("perc_autor", 0)) <= 1 else float(r.get("perc_autor", 0))),
                _money(r.get("vl_liquido", 0)),
            ]
        )
    body.append(
        [
            "",
            "",
            "",
            "",
            "TOTAL",
            f"{int(totals.get('unidades', 0)):,}".replace(",", "."),
            "",
            _money(totals.get("liquido", 0)),
        ]
    )
    col_widths = [30 * mm, 32 * mm, 22 * mm, 55 * mm, 42 * mm, 18 * mm, 18 * mm, 28 * mm]
    tbl = _detail_table(headers, body, col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, -1), (-1, -1), ACORDE_BLACK),
                ("TEXTCOLOR", (0, -1), (-1, -1), ACORDE_YELLOW),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (5, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(tbl)

    def _on_page(canvas, d):
        _header_footer(canvas, d, title, subtitle)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
