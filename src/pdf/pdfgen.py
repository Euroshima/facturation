# pdfgen.py — génération de facture avec Platypus (mise en page automatique)
# Avantages vs. canvas manuel : pagination automatique (plus de chevauchement),
# retour à la ligne automatique (plus de texte qui déborde des cadres),
# en-tête/pied de page répétés sur toutes les pages.
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
)

from core.settings import MY_INFO, CURRENCY


# --- Polices -----------------------------------------------------------------

def _register_fonts():
    """Enregistre DejaVu si disponible, sinon repli sur Helvetica.
    Retourne le couple (police normale, police grasse)."""
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
    except Exception:
        return "Helvetica", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", "DejaVuSans-Bold.ttf"))
        return "DejaVu", "DejaVu-Bold"
    except Exception:
        # Gras indisponible : on réutilise la police normale
        return "DejaVu", "DejaVu"


FONT, FONT_BOLD = _register_fonts()


# --- Helpers de formatage ----------------------------------------------------

def _fmt_money(x):
    return f"{float(x or 0):.2f} {CURRENCY}"


def _fmt_qty(qty, unit):
    s = f"{float(qty or 0):.2f}".rstrip("0").rstrip(".")
    return f"{s} kg" if unit == "kg" else f"{s} u"


def _fmt_rate(r):
    try:
        val = round(float(r or 0) * 10) / 10.0
    except (TypeError, ValueError):
        val = 0.0
    s = f"{val:.1f}"
    return s[:-2] if s.endswith(".0") else s


def _esc(text):
    """Échappe le texte issu de la base / saisi par l'utilisateur."""
    return escape("" if text is None else str(text))


def _lines_to_para(lines):
    """Assemble des lignes déjà échappées avec des sauts de ligne <br/>."""
    return "<br/>".join(lines)


# --- Styles ------------------------------------------------------------------

_STYLE_BOX_TITLE = ParagraphStyle(
    "BoxTitle", fontName=FONT_BOLD, fontSize=11, leading=14,
    textColor=colors.black, spaceAfter=2,
)
_STYLE_BOX_BODY = ParagraphStyle(
    "BoxBody", fontName=FONT, fontSize=9.5, leading=12,
    textColor=colors.black,
)
_STYLE_TH = ParagraphStyle(
    "TH", fontName=FONT_BOLD, fontSize=9.5, leading=12, alignment=TA_LEFT,
)
_STYLE_TH_R = ParagraphStyle(
    "THR", parent=_STYLE_TH, alignment=TA_RIGHT,
)
_STYLE_CELL = ParagraphStyle(
    "Cell", fontName=FONT, fontSize=9.5, leading=12, alignment=TA_LEFT,
)
_STYLE_NOTES_TITLE = ParagraphStyle(
    "NotesTitle", fontName=FONT_BOLD, fontSize=9.5, leading=12,
)
_STYLE_NOTES = ParagraphStyle(
    "Notes", fontName=FONT, fontSize=9, leading=11.5,
)

# Couleurs reprises de l'ancienne mise en page
_C_BANNER = colors.Color(0.92, 0.92, 0.95)
_C_BOX_BG = colors.Color(0.97, 0.97, 0.98)
_C_HEAD_BG = colors.Color(0.95, 0.95, 0.97)
_C_ZEBRA_1 = colors.Color(0.92, 0.92, 0.94)
_C_ZEBRA_2 = colors.Color(0.97, 0.97, 0.99)
_C_LINE = colors.Color(0.80, 0.80, 0.83)

_MARGIN = 16 * mm


# --- En-tête / pied de page (dessinés sur CHAQUE page) -----------------------

def _make_on_page(invoice):
    num = str(invoice.get("facture_num", "") or "")
    date = str(invoice.get("date", "") or "")
    rib = MY_INFO.get("rib") or "FR76 1080 7004 3362 2214 6480 324"

    def _on_page(c, doc):
        W, H = A4
        c.saveState()

        # Bandeau titre
        c.setFillColor(_C_BANNER)
        c.rect(0, H - 22 * mm, W, 22 * mm, stroke=0, fill=1)
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD, 16)
        c.drawCentredString(W / 2, H - 14 * mm, "FACTURE")
        c.setFont(FONT, 9)
        c.drawRightString(W - _MARGIN, H - 10 * mm, f"N°: {num}")
        c.drawRightString(W - _MARGIN, H - 22 * mm + 4, f"Date: {date}")

        # Bloc paiement
        c.setFont(FONT, 9)
        c.drawString(_MARGIN, 40, "Informations de paiement :")
        c.drawString(_MARGIN, 28, f"RIB : {rib}")

        c.restoreState()

    return _on_page


# --- Blocs du corps ----------------------------------------------------------

def _vendor_paragraph():
    lines = []
    for ln in (MY_INFO.get("adresse") or "").split("\n"):
        if ln.strip():
            lines.append(_esc(ln))
    if MY_INFO.get("telephone"):
        lines.append(f"Tél.: {_esc(MY_INFO['telephone'])}")
    if MY_INFO.get("email"):
        lines.append(f"Email: {_esc(MY_INFO['email'])}")
    if MY_INFO.get("siret"):
        lines.append(f"Siret: {_esc(MY_INFO['siret'])}")
    return _lines_to_para(lines)


def _client_title(client):
    title = (client.get("nom_entreprise") or "").strip()
    if not title:
        title = f"{(client.get('prenom') or '').strip()} {(client.get('nom') or '').strip()}".strip()
    return title or "Client"


def _client_paragraph(client, title):
    lines = []
    title_text = title.strip().lower()
    company = (client.get("nom_entreprise") or "").strip()
    fullname = f"{(client.get('prenom') or '').strip()} {(client.get('nom') or '').strip()}".strip()
    if company and company.lower() != title_text:
        lines.append(_esc(company))
    if fullname and fullname.lower() != title_text:
        lines.append(_esc(fullname))
    for ln in (client.get("adresse") or "").split("\n"):
        if ln.strip():
            lines.append(_esc(ln))
    if client.get("telephone"):
        lines.append(f"Tél.: {_esc(client['telephone'])}")
    if client.get("email"):
        lines.append(f"Email: {_esc(client['email'])}")
    return _lines_to_para(lines)


def _header_boxes(client, content_w):
    """Cartouches entreprise / client côte à côte : chaque cellule est un
    Paragraph, donc le texte se replie au lieu de déborder."""
    vendor_title = MY_INFO.get("nom_entreprise") or "Entreprise"
    cli_title = _client_title(client)

    left = [
        Paragraph(_esc(vendor_title), _STYLE_BOX_TITLE),
        Paragraph(_vendor_paragraph(), _STYLE_BOX_BODY),
    ]
    right = [
        Paragraph(_esc(cli_title), _STYLE_BOX_TITLE),
        Paragraph(_client_paragraph(client, cli_title), _STYLE_BOX_BODY),
    ]

    t = Table([[left, right]], colWidths=[content_w * 0.55, content_w * 0.45])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), _C_BOX_BG),
        ("BOX", (0, 0), (0, 0), 0.5, _C_LINE),
        ("BOX", (1, 0), (1, 0), 0.5, _C_LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    return t


def _items_table(items, rate, content_w):
    header = [
        Paragraph("Description", _STYLE_TH),
        Paragraph(f"Prix Unit. HT ({_esc(CURRENCY)})", _STYLE_TH_R),
        Paragraph("Quantité", _STYLE_TH_R),
        Paragraph(f"Total HT ({_esc(CURRENCY)})", _STYLE_TH_R),
        Paragraph("TVA %", _STYLE_TH_R),
    ]
    data = [header]
    for it in items:
        data.append([
            Paragraph(_esc(it.get("description")).replace("\n", "<br/>"), _STYLE_CELL),
            f"{float(it.get('price') or 0):.2f}",
            _fmt_qty(it.get("qty") or 0, it.get("unit", "kg")),
            f"{float(it.get('total') or 0):.2f}",
            f"{_fmt_rate(rate)} %",
        ])

    widths = [content_w * w for w in (0.45, 0.15, 0.15, 0.15, 0.10)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _C_HEAD_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_ZEBRA_1, _C_ZEBRA_2]),
        ("FONTNAME", (1, 1), (-1, -1), FONT),
        ("FONTSIZE", (1, 1), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _C_LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _totals_table(invoice, rate, content_w):
    panel_w = 72 * mm
    data = [
        ["Total HT", _fmt_money(invoice["subtotal"])],
        [f"TVA {_fmt_rate(rate)} %", _fmt_money(invoice["tva"])],
        ["Total TTC", _fmt_money(invoice["total"])],
    ]
    inner = Table(data, colWidths=[panel_w * 0.5, panel_w * 0.5])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_BOX_BG),
        ("FONTNAME", (0, 0), (-1, 1), FONT),
        ("FONTSIZE", (0, 0), (-1, 1), 10),
        ("FONTNAME", (0, 2), (-1, 2), FONT_BOLD),
        ("FONTSIZE", (0, 2), (-1, 2), 11),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), 0.5, _C_LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    # Table enveloppe pour aligner le panneau à droite
    wrapper = Table([[inner]], colWidths=[content_w])
    wrapper.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrapper


# --- Point d'entrée ----------------------------------------------------------

def create_pdf(invoice, client, items, path):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=34 * mm,
        bottomMargin=24 * mm,
        title=f"Facture {invoice.get('facture_num', '')}",
    )
    content_w = doc.width

    # Taux de TVA : soit fourni, soit déduit de tva/subtotal
    rate = invoice.get("tva_rate")
    if rate is None:
        try:
            rate = (float(invoice["tva"]) / float(invoice["subtotal"]) * 100) if invoice["subtotal"] else 0.0
        except Exception:
            rate = 0.0
    try:
        rate = max(0.0, float(rate))
    except Exception:
        rate = 0.0

    story = []
    story.append(_header_boxes(client, content_w))
    story.append(Spacer(1, 6 * mm))
    story.append(_items_table(items or [], rate, content_w))
    story.append(Spacer(1, 6 * mm))
    story.append(KeepTogether(_totals_table(invoice, rate, content_w)))

    if invoice.get("notes"):
        notes = _esc(invoice["notes"]).replace("\n", "<br/>")
        story.append(Spacer(1, 6 * mm))
        story.append(KeepTogether([
            Paragraph("Notes :", _STYLE_NOTES_TITLE),
            Spacer(1, 1.5 * mm),
            Paragraph(notes, _STYLE_NOTES),
        ]))

    on_page = _make_on_page(invoice)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
