# src/ui/invoice_actions.py — opérations sur une facture partagées entre onglets
from core.paths import invoice_pdf_path
from core.db import get_invoice_with_items, set_pdf_path
from pdf.pdfgen import create_pdf


def regenerate_pdf(invoice_id):
    """(Re)génère le PDF d'une facture depuis la base.
    Retourne (pdf_path, inv, client), ou (None, None, None) si introuvable."""
    inv, client, items = get_invoice_with_items(invoice_id)
    if not inv:
        return None, None, None
    pdf_path = invoice_pdf_path(client, inv["facture_num"])
    items_dict = [{"description": it["description"], "qty": float(it["qty"]),
                   "price": float(it["price"]), "unit": it.get("unit", "kg"),
                   "total": float(it["total"])} for it in items]
    try:
        tva_rate = (float(inv.get("tva", 0)) / float(inv.get("subtotal", 1))) * 100 if inv.get("subtotal") else 0.0
    except Exception:
        tva_rate = 0.0
    inv_obj = {
        "facture_num": inv.get("facture_num"),
        "date": inv.get("date"),
        "subtotal": inv.get("subtotal"),
        "tva": inv.get("tva"),
        "total": inv.get("total"),
        "notes": inv.get("notes", ""),
        "tva_rate": tva_rate,
    }
    create_pdf(inv_obj, client, items_dict, pdf_path)
    set_pdf_path(invoice_id, pdf_path)
    return pdf_path, inv, client
