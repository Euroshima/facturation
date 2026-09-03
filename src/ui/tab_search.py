import os
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY
from core.paths import invoice_pdf_path
from core.db import search_invoices, get_invoice_with_items, set_pdf_path
from pdf.pdfgen import create_pdf
from .widgets import make_sortable
from .send_email_dialog import show_send_email_dialog

class TabSearch(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        st = ttk.Frame(self)
        st.pack(fill="x", padx=6, pady=6)

        self.var_search = tk.StringVar()
        ttk.Entry(st, textvariable=self.var_search, width=50).pack(side="left", padx=4)
        ttk.Button(st, text="Rechercher", command=self._do_search).pack(side="left")
        ttk.Button(st, text="Modifier", command=self._load_selected_for_edit).pack(side="left", padx=6)
        ttk.Button(st, text="Recréer PDF", command=self._rebuild_pdf_selected).pack(side="left")
        ttk.Button(st, text="Ouvrir PDF", command=self._open_selected_pdf).pack(side="left", padx=6)
        ttk.Button(st, text="Envoyer par e-mail", command=self._email_selected).pack(side="left")

        self.tree = ttk.Treeview(
            self,
            columns=("id","num","date","client","entreprise","total","pdf"),
            show="headings", height=12
        )
        for col, title, w, anchor in [
            ("id","ID",60,"center"),
            ("num","N° Facture",140,"w"),
            ("date","Date",100,"center"),
            ("client","Client",180,"w"),
            ("entreprise","Entreprise",200,"w"),
            ("total",f"Total ({CURRENCY})",120,"e"),
            ("pdf","PDF",280,"w")
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=w, anchor=anchor)
        make_sortable(self.tree, numeric_columns=("id", "total"))
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

    # ---- Actions ----
    def _do_search(self):
        term = self.var_search.get().strip()
        rows = search_invoices(term)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            client_name = f"{r.get('prenom','')} {r.get('nom','')}".strip()
            self.tree.insert("", "end", values=(
                r.get("id"),
                r.get("facture_num"),
                r.get("date"),
                client_name,
                r.get("nom_entreprise",""),
                f"{r.get('total',0.0):.2f}",
                r.get("pdf_path","")
            ))
        self.tree.reapply_sort()

    def _load_selected_for_edit(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("Facture","Sélectionne une facture.")
        inv_id = self.tree.item(sel[0], "values")[0]
        inv, client, items = get_invoice_with_items(inv_id)

        # Remplit l’onglet création
        c = self.controller.tab_create
        c.clear_all()
        c.current_invoice_id = inv_id

        c.controller.var_c_prenom.set(client.get("prenom",""))
        c.controller.var_c_nom.set(client.get("nom",""))
        c.controller.var_c_ent.set(client.get("nom_entreprise",""))
        c.controller.var_c_addr.set(client.get("adresse",""))
        c.controller.var_c_email.set(client.get("email",""))
        c.controller.var_c_tel.set(client.get("telephone",""))
        c.controller.var_notes.set(inv.get("notes",""))
        try:
            if inv.get("subtotal"):
                c.controller.var_tva.set(f"{(float(inv.get('tva',0))/float(inv.get('subtotal',1)))*100:.2f}")
            else:
                c.controller.var_tva.set("0")
        except Exception:
            c.controller.var_tva.set("0")

        # Tableau articles
        c.items.clear()
        c.clear_items_table()
        for it in items:
            item_dict = {
                "description": it.get("description",""),
                "qty": float(it.get("qty",0)),
                "price": float(it.get("price",0)),
                "unit": it.get("unit","kg"),
                "total": float(it.get("total",0))
            }
            c.items.append(item_dict)
            total = item_dict["total"]
            c.tree.insert("", "end", values=(
                item_dict["description"],
                f"{item_dict['qty']:.2f}".rstrip("0").rstrip("."),
                item_dict["unit"],
                f"{item_dict['price']:.2f}",
                f"{total:.2f}"
            ))

        # Boutons
        c.btn_save.config(state="disabled")
        c.btn_update.config(state="normal")
        c.btn_cancel_edit.config(state="normal")
        c.refresh_totals()
        messagebox.showinfo("Édition", f"Édition de la facture {inv.get('facture_num')} (onglet Création).")

    def _regen_pdf(self, inv_id):
        """(Re)génère le PDF de la facture. Retourne (pdf_path, inv, client) ou (None, ..)."""
        inv, client, items = get_invoice_with_items(inv_id)
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
        set_pdf_path(inv_id, pdf_path)
        return pdf_path, inv, client

    def _rebuild_pdf_selected(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("PDF", "Sélectionne une facture.")
        inv_id = self.tree.item(sel[0], "values")[0]
        pdf_path, inv, _ = self._regen_pdf(inv_id)
        if not pdf_path:
            return messagebox.showerror("PDF", "Facture introuvable en base.")
        messagebox.showinfo("PDF", "PDF régénéré.")
        self.controller.open_path(pdf_path)

    def _email_selected(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("E-mail", "Sélectionne une facture.")
        inv_id = self.tree.item(sel[0], "values")[0]
        try:
            pdf_path, inv, client = self._regen_pdf(inv_id)
        except Exception as e:
            return messagebox.showerror("E-mail", f"Impossible de préparer le PDF :\n{e}")
        if not pdf_path:
            return messagebox.showerror("E-mail", "Facture introuvable en base.")
        show_send_email_dialog(
            self.winfo_toplevel(),
            facture_num=inv.get("facture_num"),
            to_addr=(client or {}).get("email", ""),
            pdf_path=pdf_path,
        )

    def _open_selected_pdf(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("PDF","Sélectionne une facture.")
        pdf = self.tree.item(sel[0], "values")[6]
        if pdf and os.path.exists(pdf):
            self.controller.open_path(pdf)
        else:
            messagebox.showerror("PDF", "Fichier introuvable.")
