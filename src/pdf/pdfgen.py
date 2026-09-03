# pdfgen.py — génération de facture avec Platypus (mise en page automatique)
# - pagination automatique (plus de chevauchement)
# - retour à la ligne automatique (plus de texte qui déborde des cadres)
# - en-tête/pied répétés, numérotation « Page X / Y »
# - formats FR (1 234,56 €, JJ/MM/AAAA), mentions légales, échéance
import datetime
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as _canvas
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
)

from core.settings import MY_INFO, CURRENCY

_DEFAULT_RIB = "FR76 1080 7004 3362 2214 6480 324"
_NBSP = " "  # espace insécable (présente dans WinAnsi / Helvetica)


# --- Polices -----------------------------------------------------------------

def _register_fonts():
    """DejaVu si dispo (Unicode complet), sinon Helvetica (accents FR OK)."""
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
    except Exception:
        return "Helvetica", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", "DejaVuSans-Bold.ttf"))
        return "DejaVu", "DejaVu-Bold"
    except Exception:
        return "DejaVu", "DejaVu"


FONT, FONT_BOLD = _register_fonts()


# --- Helpers de formatage --------------------------------------------------

def _fmt_money(x):
    """1234.5 -> '1 234,50 €' (format français)."""
    n = float(x or 0)
    s = f"{n:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", _NBSP)
    return f"{s}{_NBSP}{CURRENCY}"


def _fmt_num(x):
    """Nombre sans devise, format français."""
    n = float(x or 0)
    return f"{n:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", _NBSP)


def _fmt_qty(qty, unit):
    s = f"{float(qty or 0):.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{s}{_NBSP}kg" if unit == "kg" else f"{s}{_NBSP}u"


def _fmt_rate(r):
    try:
        val = round(float(r or 0) * 10) / 10.0
    except (TypeError, ValueError):
        val = 0.0
    s = f"{val:.1f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s


def _parse_date(d):
    """Accepte 'AAAA-MM-JJ' ou 'JJ/MM/AAAA' ou un date/datetime -> date."""
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, datetime.date):
        return d
    s = str(d or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _fmt_date(d):
    dt = _parse_date(d)
    return dt.strftime("%d/%m/%Y") if dt else str(d or "")


def _fmt_iban(v):
    v = "".join(str(v or "").split())
    return " ".join(v[i:i + 4] for i in range(0, len(v), 4)) or ""


def _esc(text):
    return escape("" if text is None else str(text))


def _lines_to_para(lines):
    return "<br/>".join(lines)


# --- Styles ----------------------------------------------------------------

_STYLE_BOX_TITLE = ParagraphStyle("BoxTitle", fontName=FONT_BOLD, fontSize=11,
                                  leading=14, textColor=colors.black, spaceAfter=2)
_STYLE_BOX_BODY = ParagraphStyle("BoxBody", fontName=FONT, fontSize=9.5, leading=12)
_STYLE_TH = ParagraphStyle("TH", fontName=FONT_BOLD, fontSize=9.5, leading=12,
                           alignment=TA_LEFT, textColor=colors.white)
_STYLE_TH_R = ParagraphStyle("THR", parent=_STYLE_TH, alignment=TA_RIGHT)
_STYLE_CELL = ParagraphStyle("Cell", fontName=FONT, fontSize=9.5, leading=12)
_STYLE_META = ParagraphStyle("Meta", fontName=FONT, fontSize=9, leading=12)
_STYLE_META_B = ParagraphStyle("MetaB", parent=_STYLE_META, fontName=FONT_BOLD)
_STYLE_NOTES_TITLE = ParagraphStyle("NotesTitle", fontName=FONT_BOLD, fontSize=9.5, leading=12)
_STYLE_NOTES = ParagraphStyle("Notes", fontName=FONT, fontSize=9, leading=11.5)
_STYLE_LEGAL = ParagraphStyle("Legal", fontName=FONT, fontSize=7.5, leading=9.5,
                              textColor=colors.Color(0.35, 0.35, 0.4))

_C_ACCENT = colors.Color(0.71, 0.20, 0.06)      # rouille Hytris (#B63410)
_C_BANNER = colors.Color(0.95, 0.95, 0.97)
_C_BOX_BG = colors.Color(0.97, 0.97, 0.98)
_C_HEAD_BG = colors.Color(0.20, 0.22, 0.28)     # en-tête tableau foncé
_C_ZEBRA_1 = colors.white
_C_ZEBRA_2 = colors.Color(0.955, 0.955, 0.97)
_C_LINE = colors.Color(0.80, 0.80, 0.83)

_MARGIN = 16 * mm


# --- Canvas numéroté (Page X / Y) ----------------------------------------

class _NumberedCanvas(_canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        self.setFont(FONT, 8)
        self.setFillColor(colors.Color(0.45, 0.45, 0.5))
        self.drawRightString(A4[0] - _MARGIN, 12 * mm,
                             f"Page {self._pageNumber} / {total}")


# --- En-tête / pied (chaque page) ---------------------------------------

def _make_on_page(invoice):
    num = str(invoice.get("facture_num", "") or "")
    issuer = MY_INFO.get("nom_entreprise") or MY_INFO.get("nom") or ""
    iban = _fmt_iban(MY_INFO.get("iban")) or (MY_INFO.get("rib") or _DEFAULT_RIB)
    bic = (MY_INFO.get("bic") or "").strip()
    extra = (MY_INFO.get("pied_de_page") or "").strip()

    def _on_page(c, doc):
        W, H = A4
        c.saveState()

        # Bandeau
        c.setFillColor(_C_BANNER)
        c.rect(0, H - 24 * mm, W, 24 * mm, stroke=0, fill=1)
        c.setFillColor(_C_ACCENT)
        c.rect(0, H - 24 * mm, W, 1.4 * mm, stroke=0, fill=1)
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD, 17)
        c.drawString(_MARGIN, H - 14 * mm, "FACTURE")
        if issuer:
            c.setFont(FONT, 9)
            c.setFillColor(colors.Color(0.35, 0.35, 0.4))
            c.drawString(_MARGIN, H - 19.5 * mm, issuer)
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD, 11)
        c.drawRightString(W - _MARGIN, H - 13 * mm, f"N° {num}")
        c.setFont(FONT, 9)
        c.setFillColor(colors.Color(0.35, 0.35, 0.4))
        c.drawRightString(W - _MARGIN, H - 19.5 * mm, _fmt_date(invoice.get("date")))

        # Pied : coordonnées bancaires
        c.setFillColor(_C_LINE)
        c.rect(_MARGIN, 20 * mm, W - 2 * _MARGIN, 0.4, stroke=0, fill=1)
        c.setFillColor(colors.Color(0.35, 0.35, 0.4))
        c.setFont(FONT, 8)
        pay = f"Règlement par virement — IBAN : {iban}"
        if bic:
            pay += f"   BIC : {bic}"
        c.drawString(_MARGIN, 15 * mm, pay)
        if extra:
            c.drawString(_MARGIN, 11 * mm, extra)

        c.restoreState()

    return _on_page


# --- Blocs du corps ----------------------------------------------------

def _vendor_paragraph():
    lines = [_esc(ln) for ln in (MY_INFO.get("adresse") or "").split("\n") if ln.strip()]
    if MY_INFO.get("telephone"):
        lines.append(f"Tél. : {_esc(MY_INFO['telephone'])}")
    if MY_INFO.get("email"):
        lines.append(f"Email : {_esc(MY_INFO['email'])}")
    if MY_INFO.get("siret"):
        lines.append(f"SIRET : {_esc(MY_INFO['siret'])}")
    if MY_INFO.get("tva_intracom"):
        lines.append(f"TVA : {_esc(MY_INFO['tva_intracom'])}")
    return _lines_to_para(lines)


def _client_title(client):
    title = (client.get("nom_entreprise") or "").strip()
    if not title:
        title = f"{(client.get('prenom') or '').strip()} {(client.get('nom') or '').strip()}".strip()
    return title or "Client"


def _client_paragraph(client, title):
    lines = []
    tl = title.strip().lower()
    company = (client.get("nom_entreprise") or "").strip()
    fullname = f"{(client.get('prenom') or '').strip()} {(client.get('nom') or '').strip()}".strip()
    if company and company.lower() != tl:
        lines.append(_esc(company))
    if fullname and fullname.lower() != tl:
        lines.append(_esc(fullname))
    for ln in (client.get("adresse") or "").split("\n"):
        if ln.strip():
            lines.append(_esc(ln))
    if client.get("telephone"):
        lines.append(f"Tél. : {_esc(client['telephone'])}")
    if client.get("email"):
        lines.append(f"Email : {_esc(client['email'])}")
    return _lines_to_para(lines)


def _header_boxes(client, content_w):
    left = [
        Paragraph("Émetteur", _STYLE_BOX_TITLE),
        Paragraph(_esc(MY_INFO.get("nom_entreprise") or "Entreprise"), _STYLE_META_B),
        Spacer(1, 1 * mm),
        Paragraph(_vendor_paragraph(), _STYLE_BOX_BODY),
    ]
    cli_title = _client_title(client)
    right = [
        Paragraph("Client", _STYLE_BOX_TITLE),
        Paragraph(_esc(cli_title), _STYLE_META_B),
        Spacer(1, 1 * mm),
        Paragraph(_client_paragraph(client, cli_title), _STYLE_BOX_BODY),
    ]
    t = Table([[left, right]], colWidths=[content_w * 0.52, content_w * 0.48])
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


def _meta_row(invoice, content_w):
    """Ligne Date d'émission / Échéance / Référence."""
    d = _parse_date(invoice.get("date")) or datetime.date.today()
    try:
        delai = int(MY_INFO.get("delai_paiement_jours", 30))
    except (TypeError, ValueError):
        delai = 30
    echeance = invoice.get("echeance") or (d + datetime.timedelta(days=delai)).strftime("%Y-%m-%d")
    ref = (invoice.get("reference") or MY_INFO.get("reference_client") or "").strip()

    cells = [
        [Paragraph("Date d'émission", _STYLE_META), Paragraph(_fmt_date(d), _STYLE_META_B)],
        [Paragraph("Échéance", _STYLE_META), Paragraph(_fmt_date(echeance), _STYLE_META_B)],
    ]
    if ref:
        cells.append([Paragraph("Référence", _STYLE_META), Paragraph(_esc(ref), _STYLE_META_B)])

    t = Table([sum(cells, [])], colWidths=_meta_widths(len(cells), content_w))
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _meta_widths(n, content_w):
    each = content_w / n
    return [each * 0.42, each * 0.58] * n


def _items_table(items, rate, content_w):
    header = [
        Paragraph("Description", _STYLE_TH),
        Paragraph(f"P.U. HT ({_esc(CURRENCY)})", _STYLE_TH_R),
        Paragraph("Qté", _STYLE_TH_R),
        Paragraph(f"Total HT ({_esc(CURRENCY)})", _STYLE_TH_R),
    ]
    data = [header]
    for it in items:
        data.append([
            Paragraph(_esc(it.get("description")).replace("\n", "<br/>"), _STYLE_CELL),
            _fmt_num(it.get("price")),
            _fmt_qty(it.get("qty"), it.get("unit", "kg")),
            _fmt_num(it.get("total")),
        ])
    widths = [content_w * w for w in (0.55, 0.15, 0.13, 0.17)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _C_HEAD_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_ZEBRA_1, _C_ZEBRA_2]),
        ("FONTNAME", (1, 1), (-1, -1), FONT),
        ("FONTSIZE", (1, 1), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, _C_LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, _C_HEAD_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _totals_table(invoice, rate, content_w):
    panel_w = 78 * mm
    subtotal = invoice.get("subtotal")
    tva = invoice.get("tva")
    total = invoice.get("total")
    franchise = (float(rate or 0) == 0.0) and (float(tva or 0) == 0.0)

    rows = [["Total HT", _fmt_money(subtotal)]]
    if franchise:
        rows.append(["TVA", "non applicable"])
    else:
        rows.append([f"TVA {_fmt_rate(rate)} %", _fmt_money(tva)])
    rows.append(["Net à payer TTC", _fmt_money(total)])

    inner = Table(rows, colWidths=[panel_w * 0.52, panel_w * 0.48])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -2), _C_BOX_BG),
        ("BACKGROUND", (0, -1), (-1, -1), _C_HEAD_BG),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -2), FONT),
        ("FONTSIZE", (0, 0), (-1, -2), 10),
        ("FONTNAME", (0, -1), (-1, -1), FONT_BOLD),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    wrapper = Table([[inner]], colWidths=[content_w])
    wrapper.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def _legal_block(rate, tva):
    override = (MY_INFO.get("mentions_legales") or "").strip()
    if override:
        parts = [override]
    else:
        parts = [
            "Conditions de règlement : paiement à réception de facture, par virement bancaire.",
            "En cas de retard de paiement, une pénalité égale à trois fois le taux d'intérêt "
            "légal sera exigible (art. L.441-10 du Code de commerce), ainsi qu'une indemnité "
            "forfaitaire pour frais de recouvrement de 40 € (art. D.441-5). Pas d'escompte "
            "pour paiement anticipé.",
        ]
        if float(rate or 0) == 0.0 and float(tva or 0) == 0.0:
            parts.insert(0, "TVA non applicable, article 293 B du CGI.")
    return [Paragraph(_esc(p), _STYLE_LEGAL) for p in parts]


# --- Point d'entrée --------------------------------------------------------

def create_pdf(invoice, client, items, path):
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=32 * mm, bottomMargin=26 * mm,
        title=f"Facture {invoice.get('facture_num', '')}",
        author=MY_INFO.get("nom_entreprise") or MY_INFO.get("nom") or "",
    )
    content_w = doc.width

    rate = invoice.get("tva_rate")
    if rate is None:
        try:
            rate = (float(invoice["tva"]) / float(invoice["subtotal"]) * 100) if invoice.get("subtotal") else 0.0
        except Exception:
            rate = 0.0
    try:
        rate = max(0.0, float(rate))
    except Exception:
        rate = 0.0

    story = [
        _header_boxes(client, content_w),
        Spacer(1, 4 * mm),
        _meta_row(invoice, content_w),
        Spacer(1, 5 * mm),
        _items_table(items or [], rate, content_w),
        Spacer(1, 5 * mm),
        KeepTogether(_totals_table(invoice, rate, content_w)),
    ]

    if invoice.get("notes"):
        notes = _esc(invoice["notes"]).replace("\n", "<br/>")
        story += [Spacer(1, 6 * mm), KeepTogether([
            Paragraph("Notes", _STYLE_NOTES_TITLE),
            Spacer(1, 1.5 * mm),
            Paragraph(notes, _STYLE_NOTES),
        ])]

    story += [Spacer(1, 8 * mm), KeepTogether(_legal_block(rate, invoice.get("tva")))]

    on_page = _make_on_page(invoice)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page,
              canvasmaker=_NumberedCanvas)
