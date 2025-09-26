# pdfgen.py — lignes zebra avec padding vertical, unité intégrée dans quantité, marges égales, texte centré verticalement
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from core.settings import MY_INFO, CURRENCY

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

def _fmt_qty(qty, unit):
    s = f"{float(qty):.2f}".rstrip("0").rstrip(".")
    return f"{s} kg" if unit=="kg" else f"{s} u"

def _fmt_rate(r):
    val = round(float(r) * 10) / 10.0
    s = f"{val:.1f}"
    return s[:-2] if s.endswith(".0") else s

def create_pdf(invoice, client, items, path):
    font = _register_font()
    c = canvas.Canvas(path, pagesize=A4)
    W, H = A4

    # Marges
    M = 16*mm

    # Bandeau titre
    c.setFillColorRGB(0.92,0.92,0.95)
    c.rect(0,H-22*mm,W,22*mm,stroke=0,fill=1)
    c.setFillColor(colors.black)
    c.setFont(font,16)
    c.drawCentredString(W/2,H-14*mm,"FACTURE")
    c.setFont(font,9)
    c.drawRightString(W-M,H-10*mm,f"N°: {invoice['facture_num']}")
    c.drawRightString(W-M,H-22*mm+4,f"Date: {invoice['date']}")

    # Cartouches entreprise/client
    box_h = 40*mm
    vend_x,vend_w = M,90*mm
    cli_w = 80*mm
    cli_x = W-M-cli_w
    vend_y = H-22*mm-6*mm-box_h
    cli_y = vend_y

    def draw_box(x,y,w,h,title):
        c.setFillColorRGB(0.97,0.97,0.98)
        c.roundRect(x,y,w,h,4,stroke=1,fill=1)
        c.setFillColor(colors.black)
        c.setFont(font,11)
        c.drawString(x+4*mm,y+h-6*mm,title)

    draw_box(vend_x,vend_y,vend_w,box_h,MY_INFO.get("nom_entreprise") or "Entreprise")
    client_title = (client.get("nom_entreprise") or "").strip()
    if not client_title:
        client_title = f"{(client.get('prenom') or '').strip()} {(client.get('nom') or '').strip()}".strip() or "Client"
    draw_box(cli_x,cli_y,cli_w,box_h,client_title)

    # Contenu entreprise
    c.setFont(font,10)
    y = vend_y + box_h - 12*mm
    for ln in (MY_INFO.get("adresse","").split("\n") if MY_INFO.get("adresse") else []):
        if ln: c.drawString(vend_x+4*mm,y,ln); y-=12
    if MY_INFO.get("telephone"): c.drawString(vend_x+4*mm,y,f"Tél.: {MY_INFO['telephone']}"); y-=12
    if MY_INFO.get("email"):     c.drawString(vend_x+4*mm,y,f"Email: {MY_INFO['email']}"); y-=12
    if MY_INFO.get("siret"):     c.drawString(vend_x+4*mm,y,f"Siret: {MY_INFO['siret']}"); y-=12

    # Contenu client
    y = cli_y+box_h-12*mm
    client_fullname = f"{(client.get('prenom') or '').strip()} {(client.get('nom') or '').strip()}".strip()
    client_company  = (client.get("nom_entreprise") or "").strip()
    title_text = client_title.strip().lower()
    if client_company and client_company.strip().lower() != title_text:
        c.drawString(cli_x+4*mm,y,client_company); y-=12
    if client_fullname and client_fullname.strip().lower() != title_text:
        c.drawString(cli_x+4*mm,y,client_fullname); y-=12
    for ln in (client.get("adresse") or "").split("\n"):
        if ln: c.drawString(cli_x+4*mm,y,ln); y-=12
    if client.get("telephone"):
        c.drawString(cli_x+4*mm,y,f"Tél.: {client['telephone']}"); y-=12
    if client.get("email"):
        c.drawString(cli_x+4*mm,y,f"Email: {client['email']}"); y-=12

    # Tableau
    table_top = vend_y - 14*mm

    # Largeur tableau = largeur page - 2*M pour avoir marge égale
    total_w = W - 2*M

    # Colonnes proportionnelles
    w_desc = 0.45*total_w
    w_pu   = 0.15*total_w
    w_qty  = 0.15*total_w
    w_tht  = 0.15*total_w
    w_tva  = 0.10*total_w

    col_desc_l = M
    col_desc_r = col_desc_l + w_desc
    col_pu_r   = col_desc_r + w_pu
    col_qty_r  = col_pu_r + w_qty
    col_tht_r  = col_qty_r + w_tht
    col_tva_r  = col_tht_r + w_tva

    header_h = 16
    c.setFillColorRGB(0.95,0.95,0.97)
    c.roundRect(M,table_top-header_h,total_w,header_h,3,stroke=0,fill=1)
    c.setFillColor(colors.black)
    c.setFont(font,9.5)
    c.drawString(col_desc_l+2,table_top-10,"Description")
    c.drawRightString(col_pu_r-2,table_top-10,f"Prix Unit. HT ({CURRENCY})")
    c.drawRightString(col_qty_r-2,table_top-10,"Quantité")
    c.drawRightString(col_tht_r-2,table_top-10,f"Total HT ({CURRENCY})")
    c.drawRightString(col_tva_r-2,table_top-10,"TVA %")

    y = table_top-header_h-4
    row_h = 16
    row_padding = 4  # padding vertical
    bottom_margin = M+90
    rate = invoice.get("tva_rate")
    if rate is None:
        try: rate = (float(invoice["tva"])/float(invoice["subtotal"])*100) if invoice["subtotal"] else 0.0
        except: rate=0.0
    rate=max(0.0,float(rate))

    for idx,it in enumerate(items):
        lines = _wrap(it["description"],w_desc-6,font,9.5)
        block_h = row_h*max(1,len(lines)) + row_padding
        if y-block_h<bottom_margin:
            c.showPage()
            y=H-22*mm-6*mm-40*mm-10*mm

        # Ligne zebra
        bg_color = (0.92,0.92,0.94) if idx%2==0 else (0.97,0.97,0.99)
        c.setFillColorRGB(*bg_color)
        c.rect(M,y-block_h+row_padding/2,total_w,block_h-row_padding,stroke=0,fill=1)
        c.setFillColor(colors.black)

        qty_str = _fmt_qty(it["qty"],it.get("unit","kg"))
        pu = float(it["price"])
        tht = float(it["total"])

        # Centrage vertical du texte dans la ligne
        line_offset = (block_h - row_padding - row_h*len(lines))/2

        for i,ln in enumerate(lines):
            y_line = y - row_padding/2 - line_offset - i*row_h - row_h/2 + 2  # +2 ajuste le centrage
            c.setFont(font,9.5)
            c.drawString(col_desc_l+2,y_line,ln)
            if i==0:
                c.drawRightString(col_pu_r-2,y_line,f"{pu:.2f}")
                c.drawRightString(col_qty_r-2,y_line,qty_str)
                c.drawRightString(col_tht_r-2,y_line,f"{tht:.2f}")
                c.drawRightString(col_tva_r-2,y_line,f"{_fmt_rate(rate)} %")

        y -= block_h
        c.setStrokeColorRGB(0.80,0.80,0.83)
        c.line(M+0.3*mm,y+2,M+total_w-0.3*mm,y+2)
        c.setStrokeColor(colors.black)

    # Totaux
    panel_w = 72*mm
    px = W-M-panel_w
    py = y-10
    c.setFillColorRGB(0.97,0.97,0.98)
    c.roundRect(px,py-60,panel_w,60,4,stroke=0,fill=1)
    c.setFillColor(colors.black)
    c.setFont(font,10)
    c.drawString(px+5*mm,py-14,"Total HT")
    c.drawRightString(W-M,py-14,_fmt_money(invoice["subtotal"]))
    c.drawString(px+5*mm,py-28,f"TVA {_fmt_rate(rate)} %")
    c.drawRightString(W-M,py-28,_fmt_money(invoice["tva"]))
    c.setFont(font,11)
    c.drawString(px+5*mm,py-44,"Total TTC")
    c.drawRightString(W-M,py-44,_fmt_money(invoice["total"]))

    if invoice.get("notes"):
        c.setFont(font,9)
        notes_top = py-80
        c.drawString(M,notes_top,"Notes :")
        t=c.beginText(M,notes_top-12)
        t.setFont(font,9)
        for ln in (invoice["notes"] or "").split("\n"):
            t.textLine(ln)
        c.drawText(t)

    # Bloc paiement
    rib = MY_INFO.get("rib","FR76 1080 7004 3362 2214 6480 324")
    c.setFont(font,9)
    c.drawString(M,40,"Informations de paiement :")
    c.drawString(M,28,f"RIB : {rib}")

    c.showPage()
    c.save()
