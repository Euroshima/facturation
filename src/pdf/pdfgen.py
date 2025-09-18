# pdfgen.py — lignes à fond sombre, sans gros nom d'entreprise, sans pied "Prestation de service"
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from core.settings import MY_INFO, CURRENCY

# ---------- utils ----------
def _register_font():
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
        return "DejaVu"
    except Exception:
        return "Helvetica"

def _wrap(text, max_width, font, size):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= max_width:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [""]

def _fmt_money(x):
    return f"{float(x):.2f} {CURRENCY}"

def _fmt_qty(x):
    s = f"{float(x):.2f}"
    return s.rstrip("0").rstrip(".")

def _fmt_rate(r):
    val = round(float(r) * 10) / 10.0
    s = f"{val:.1f}"
    return s[:-2] if s.endswith(".0") else s

# ---------- main ----------
def create_pdf(invoice, client, items, path):
    """
    invoice: facture_num, date, subtotal, tva, total, notes, tva_rate (optionnel)
    """
    font = _register_font()
    c = canvas.Canvas(path, pagesize=A4)
    W, H = A4
    M = 16 * mm

    # Bandeau de titre
    c.setFillColorRGB(0.92, 0.92, 0.95)
    c.rect(0, H - 22*mm, W, 22*mm, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont(font, 16)
    c.drawCentredString(W/2, H - 14*mm, "FACTURE")
    c.setFont(font, 9)
    c.drawRightString(W - M, H - 10*mm, f"N°: {invoice['facture_num']}")
    c.drawRightString(W - M, H - 22*mm + 4, f"Date: {invoice['date']}")

    # Cartouches
    box_h = 40 * mm
    vend_x, vend_w = M, 90*mm
    cli_w = 80*mm
    cli_x = W - M - cli_w
    vend_y = H - 22*mm - 6*mm - box_h
    cli_y = vend_y

    def draw_box(x, y, w, h, title):
        c.setFillColorRGB(0.97, 0.97, 0.98)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
        c.setFillColor(colors.black)
        c.setFont(font, 11)
        c.drawString(x + 4*mm, y + h - 6*mm, title)

    # Nom de l’entreprise (settings)
    ent_title = MY_INFO.get("nom_entreprise") or "Entreprise"
    draw_box(vend_x, vend_y, vend_w, box_h, ent_title)

    # Nom du client ou son entreprise
    client_title = (client["nom_entreprise"] or "").strip()
    if not client_title:
        client_title = f"{(client['prenom'] or '').strip()} {(client['nom'] or '').strip()}".strip() or "Client"
    draw_box(cli_x, cli_y, cli_w, box_h, client_title)

    # contenu entreprise —> SANS le gros nom de l'entreprise
    c.setFont(font, 10)
    y = vend_y + box_h - 12*mm
    for ln in (MY_INFO.get("adresse","").split("\n") if MY_INFO.get("adresse") else []):
        if ln: c.drawString(vend_x + 4*mm, y, ln); y -= 12
    if MY_INFO.get("telephone"): c.drawString(vend_x + 4*mm, y, f"Tél.: {MY_INFO['telephone']}"); y -= 12
    if MY_INFO.get("email"):     c.drawString(vend_x + 4*mm, y, f"Email: {MY_INFO['email']}"); y -= 12
    if MY_INFO.get("siret"):     c.drawString(vend_x + 4*mm, y, f"Siret: {MY_INFO['siret']}"); y -= 12

    # contenu client (évite les doublons avec le titre)
    y = cli_y + box_h - 12*mm
    client_fullname = f"{(client['prenom'] or '').strip()} {(client['nom'] or '').strip()}".strip()
    client_company  = (client["nom_entreprise"] or "").strip()
    title_text = client_title.strip().lower()

    if client_company and client_company.strip().lower() != title_text:
        c.drawString(cli_x + 4*mm, y, client_company); y -= 12
    if client_fullname and client_fullname.strip().lower() != title_text:
        c.drawString(cli_x + 4*mm, y, client_fullname); y -= 12
    for ln in (client["adresse"] or "").split("\n"):
        if ln: c.drawString(cli_x + 4*mm, y, ln); y -= 12
    if client["telephone"]:
        c.drawString(cli_x + 4*mm, y, f"Tél.: {client['telephone']}"); y -= 12
    if client["email"]:
        c.drawString(cli_x + 4*mm, y, f"Email: {client['email']}"); y -= 12

    # Tableau
    table_top = vend_y - 14*mm
    left, right = M, W - M

    w_desc, w_pu, w_qty, w_tot_ht, w_tva = 100, 28, 18, 28, 18
    total_w = (w_desc + w_pu + w_qty + w_tot_ht + w_tva) * mm
    start_x = left + max(0, ((right - left) - total_w) / 2.0)

    col_desc_l = start_x
    col_desc_r = start_x + w_desc*mm
    col_pu_r   = col_desc_r + w_pu*mm
    col_qty_r  = col_pu_r   + w_qty*mm
    col_tht_r  = col_qty_r  + w_tot_ht*mm
    col_tva_r  = col_tht_r  + w_tva*mm

    header_h = 16
    c.setFillColorRGB(0.95, 0.95, 0.97)
    c.roundRect(start_x, table_top - 10, total_w, header_h, 3, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont(font, 9.5)
    c.drawString(col_desc_l + 2, table_top - 6, "Description")
    c.drawRightString(col_pu_r - 2,   table_top - 6, f"Prix Unit. HT ({CURRENCY})")
    c.drawRightString(col_qty_r - 2,  table_top - 6, "Quantité")
    c.drawRightString(col_tht_r - 2,  table_top - 6, f"Total HT ({CURRENCY})")
    c.drawRightString(col_tva_r - 2,  table_top - 6, "TVA %")

    y = table_top - 20
    row_h = 16

    rate = invoice.get("tva_rate")
    if rate is None:
        try:
            rate = (float(invoice["tva"]) / float(invoice["subtotal"])) * 100 if invoice["subtotal"] else 0.0
        except Exception:
            rate = 0.0
    rate = max(0.0, float(rate))

    bottom_guard = M + 90
    c.setLineWidth(0.4)
    c.setLineCap(1)
    sep_margin = 0.3 * mm

    # Couleur de fond sombre pour TOUTES les lignes
    row_bg = (0.92, 0.92, 0.94)

    for idx, it in enumerate(items):
        max_w_desc = col_desc_r - col_desc_l - 6
        lines = _wrap(it["description"], max_w_desc, font, 9.5)
        block_h = row_h * max(1, len(lines))
        if y - block_h < bottom_guard:
            break

        c.setFillColorRGB(*row_bg)
        c.rect(start_x, y + 4 - block_h, total_w, block_h, stroke=0, fill=1)
        c.setFillColor(colors.black)

        qty = float(it["qty"])
        pu  = float(it["price"])
        tht = float(it["total"])

        for i, ln in enumerate(lines):
            c.setFont(font, 9.5)
            c.drawString(col_desc_l + 2, y, ln)
            if i == 0:
                c.drawRightString(col_pu_r - 2,   y, f"{pu:.2f}")
                c.drawRightString(col_qty_r - 2,  y, _fmt_qty(qty))
                c.drawRightString(col_tht_r - 2,  y, f"{tht:.2f}")
                c.drawRightString(col_tva_r - 2,  y, f"{_fmt_rate(rate)} %")
            y -= row_h

        c.setStrokeColorRGB(0.80, 0.80, 0.83)
        c.line(start_x + sep_margin, y + 4, start_x + total_w - sep_margin, y + 4)
        c.setStrokeColor(colors.black)

    # Totaux
    panel_w = 72*mm
    px = right - panel_w
    py = y - 10
    c.setFillColorRGB(0.97, 0.97, 0.98)
    c.roundRect(px, py - 60, panel_w, 60, 4, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont(font, 10)
    c.drawString(px + 5*mm, py - 14, "Total HT")
    c.drawRightString(right - 4, py - 14, _fmt_money(invoice["subtotal"]))
    c.drawString(px + 5*mm, py - 28, f"TVA {_fmt_rate(rate)} %")
    c.drawRightString(right - 4, py - 28, _fmt_money(invoice["tva"]))
    c.setFont(font, 11)
    c.drawString(px + 5*mm, py - 44, "Total TTC")
    c.drawRightString(right - 4, py - 44, _fmt_money(invoice["total"]))

    # Notes éventuelles
    if invoice.get("notes"):
        c.setFont(font, 9)
        notes_top = py - 80
        c.drawString(M, notes_top, "Notes :")
        t = c.beginText(M, notes_top - 12)
        t.setFont(font, 9)
        for ln in (invoice["notes"] or "").split("\n"):
            t.textLine(ln)
        c.drawText(t)

    c.showPage()
    c.save()
