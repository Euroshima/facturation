import os
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY, PDF_FOLDER
from core.db import search_invoices, get_invoice_with_items, set_pdf_path
from pdf.pdfgen import create_pdf

class TabSearch(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        st = ttk.Frame(self); st.pack(fill="x", padx=6, pady=6)
        self.var_search = tk.StringVar()
        ttk.Entry(st, textvariable=self.var_search, width=50).pack(side="left", padx=4)
        ttk.Button(st, text="Rechercher", command=self._do_search).pack(side="left")
        ttk.Button(st, text="Modifier", command=self._load_selected_for_edit).pack(side="left", padx=6)
        ttk.Button(st, text="Recréer PDF", command=self._rebuild_pdf_selected).pack(side="left")
        ttk.Button(st, text="Ouvrir PDF", command=self._open_selected_pdf).pack(side="left", padx=6)

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
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

    # ---- actions
    def _do_search(self):
        term = self.var_search.get().strip()
        rows = search_invoices(term)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            client_name = f"{r['prenom']} {r['nom']}".strip()
            self.tree.insert("", "end", values=(
                r["id"], r["facture_num"], r["date"], client_name,
                r["nom_entreprise"] or "", f"{r['total']:.2f}", r["pdf_path"] or ""
            ))

    def _load_selected_for_edit(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("Facture","Sélectionne une facture.")
        inv_id = self.tree.item(sel[0], "values")[0]
        inv, client, items = get_invoice_with_items(inv_id)

        # Remplit les champs dans l’onglet création
        c = self.controller
        c.current_invoice_id = inv_id
        c.var_c_prenom.set(client["prenom"] or "")
        c.var_c_nom.set(client["nom"] or "")
        c.var_c_ent.set(client["nom_entreprise"] or "")
        c.var_c_addr.set(client["adresse"] or "")
        c.var_c_email.set(client["email"] or "")
        c.var_c_tel.set(client["telephone"] or "")
        c.var_notes.set(inv["notes"] or "")
        try:
            if inv["subtotal"]:
                c.var_tva.set(f"{(float(inv['tva'])/float(inv['subtotal']))*100:.2f}")
            else:
                c.var_tva.set("0")
        except:
            c.var_tva.set("0")

        # Alimente le tableau des articles
        c.items.clear()
        self.controller.tab_create.clear_items_table()
        for it in items:
            d = {"description": it["description"], "qty": float(it["qty"]), "price": float(it["price"]), "total": float(it["total"])}
            c.items.append(d)
            self.controller.tab_create.tree.insert(
                "", "end",
                values=(d["description"], f"{d['qty']:.2f}".rstrip('0').rstrip('.'),
                        f"{d['price']:.2f}", f"{d['total']:.2f}")
            )

        # Boutons
        self.controller.tab_create.btn_save.config(state="disabled")
        self.controller.tab_create.btn_update.config(state="normal")
        self.controller.tab_create.btn_cancel_edit.config(state="normal")
        self.controller.tab_create.refresh_totals()
        messagebox.showinfo("Édition", f"Édition de la facture {inv['facture_num']} (onglet Création).")

    def _rebuild_pdf_selected(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("PDF","Sélectionne une facture.")
        inv_id = self.tree.item(sel[0], "values")[0]
        inv, client, items = get_invoice_with_items(inv_id)
        pdf_path = os.path.join(PDF_FOLDER, f"facture_{inv['facture_num']}.pdf")
        items_dict = [{"description": it["description"], "qty": float(it["qty"]), "price": float(it["price"]), "total": float(it["total"])} for it in items]
        try:
            tva_rate = (float(inv["tva"]) / float(inv["subtotal"])) * 100 if inv["subtotal"] else 0.0
        except Exception:
            tva_rate = 0.0
        inv_obj = {
            "facture_num": inv["facture_num"],
            "date": inv["date"],
            "subtotal": inv["subtotal"],
            "tva": inv["tva"],
            "total": inv["total"],
            "notes": inv["notes"] or "",
            "tva_rate": tva_rate,
        }
        create_pdf(inv_obj, client, items_dict, pdf_path)
        set_pdf_path(inv_id, pdf_path)
        messagebox.showinfo("PDF", "PDF régénéré.")
        self.controller.open_path(pdf_path)

    def _open_selected_pdf(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("PDF","Sélectionne une facture.")
        pdf = self.tree.item(sel[0], "values")[6]
        if pdf and os.path.exists(pdf):
            self.controller.open_path(pdf)
        else:
            messagebox.showerror("PDF", "Fichier introuvable.")
