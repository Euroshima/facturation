import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY, PDF_FOLDER
from core.db import (
    money, update_client, find_or_create_client,
    generate_invoice_number, insert_invoice, update_invoice,
    set_pdf_path, get_invoice_with_items, search_clients
)
from pdf.pdfgen import create_pdf
from .widgets import SuggestPopup

class TabCreate(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.items = self.controller.items
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        # Bloc client
        fr_client = ttk.LabelFrame(self, text="Client")
        fr_client.pack(fill="x", padx=6, pady=6)

        row=0
        ttk.Label(fr_client, text="Prénom").grid(row=row, column=0, sticky="w")
        e_prenom = ttk.Entry(fr_client, textvariable=self.controller.var_c_prenom, width=20)
        e_prenom.grid(row=row, column=1, padx=4, pady=2)

        ttk.Label(fr_client, text="Nom").grid(row=row, column=2, sticky="w")
        e_nom = ttk.Entry(fr_client, textvariable=self.controller.var_c_nom, width=20)
        e_nom.grid(row=row, column=3, padx=4, pady=2)

        ttk.Label(fr_client, text="Entreprise").grid(row=row, column=4, sticky="w")
        e_ent = ttk.Entry(fr_client, textvariable=self.controller.var_c_ent, width=28)
        e_ent.grid(row=row, column=5, padx=4, pady=2)

        row+=1
        ttk.Label(fr_client, text="Adresse").grid(row=row, column=0, sticky="w")
        ttk.Entry(fr_client, textvariable=self.controller.var_c_addr, width=70).grid(row=row, column=1, columnspan=5, sticky="we", padx=4, pady=2)

        row+=1
        ttk.Label(fr_client, text="Email").grid(row=row, column=0, sticky="w")
        ttk.Entry(fr_client, textvariable=self.controller.var_c_email, width=25).grid(row=row, column=1, padx=4, pady=2)
        ttk.Label(fr_client, text="Téléphone").grid(row=row, column=2, sticky="w")
        ttk.Entry(fr_client, textvariable=self.controller.var_c_tel, width=20).grid(row=row, column=3, padx=4, pady=2)

        btns = ttk.Frame(fr_client); btns.grid(row=row, column=4, columnspan=2, sticky="e")
        ttk.Button(btns, text="Enregistrer/MAJ client", command=self._save_client_only).pack(side="left", padx=4)

        for i in range(6):
            fr_client.columnconfigure(i, weight=1)

        # autocomplétion
        self.popup_nom = SuggestPopup(e_nom, self._choose_suggestion)
        self.popup_ent = SuggestPopup(e_ent, self._choose_suggestion)
        e_nom.bind("<KeyRelease>", lambda e: self._update_suggestions("nom"))
        e_ent.bind("<KeyRelease>", lambda e: self._update_suggestions("entreprise"))
        e_nom.bind("<FocusOut>", lambda e: self.popup_nom.hide())
        e_ent.bind("<FocusOut>", lambda e: self.popup_ent.hide())

        # Articles
        fr_items = ttk.LabelFrame(self, text="Articles")
        fr_items.pack(fill="both", padx=6, pady=6, expand=True)

        self.var_i_desc = tk.StringVar()
        self.var_i_qty = tk.StringVar(value="1")
        self.var_i_price = tk.StringVar(value="0.00")

        top = ttk.Frame(fr_items); top.pack(fill="x", padx=4, pady=4)
        ttk.Entry(top, textvariable=self.var_i_desc, width=60).pack(side="left", padx=4)
        ttk.Entry(top, textvariable=self.var_i_qty, width=8).pack(side="left", padx=4)
        ttk.Entry(top, textvariable=self.var_i_price, width=12).pack(side="left", padx=4)
        ttk.Button(top, text="Ajouter", command=self._add_item).pack(side="left", padx=4)
        ttk.Button(top, text="Supprimer sélection", command=self._remove_selected_item).pack(side="left", padx=4)

        self.tree = ttk.Treeview(fr_items, columns=("desc","qty","price","total"), show="headings", height=8)
        self.tree.heading("desc", text="Description")
        self.tree.heading("qty", text="Qté")
        self.tree.heading("price", text=f"Prix unit. ({CURRENCY})")
        self.tree.heading("total", text=f"Total ({CURRENCY})")
        self.tree.column("desc", width=500)
        self.tree.column("qty", width=60, anchor="e")
        self.tree.column("price", width=120, anchor="e")
        self.tree.column("total", width=120, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Totaux + Notes
        bottom = ttk.Frame(self); bottom.pack(fill="x", padx=6, pady=6)
        left = ttk.Frame(bottom); left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="TVA (%)").pack(side="left")
        e_tva = ttk.Entry(left, textvariable=self.controller.var_tva, width=8)
        e_tva.pack(side="left", padx=4)
        ttk.Label(left, text="Notes").pack(side="left")
        ttk.Entry(left, textvariable=self.controller.var_notes, width=50).pack(side="left", padx=4)

        right = ttk.Frame(bottom); right.pack(side="right")
        self.lbl_ht  = ttk.Label(right, text=f"HT: 0.00 {CURRENCY}")
        self.lbl_tva = ttk.Label(right, text=f"TVA: 0.00 {CURRENCY}")
        self.lbl_ttc = ttk.Label(right, text=f"TTC: 0.00 {CURRENCY}", font=("TkDefaultFont",10,"bold"))
        self.lbl_ht.grid(row=0, column=0, sticky="e", padx=8)
        self.lbl_tva.grid(row=1, column=0, sticky="e", padx=8)
        self.lbl_ttc.grid(row=2, column=0, sticky="e", padx=8)

        actions = ttk.Frame(self); actions.pack(fill="x", padx=6, pady=6)
        self.btn_save = ttk.Button(actions, text="Générer PDF & Enregistrer (NOUVELLE facture)", command=self._create_invoice)
        self.btn_save.pack(side="right")
        self.btn_update = ttk.Button(actions, text="Enregistrer modifications (facture existante)", command=self._save_edit, state="disabled")
        self.btn_update.pack(side="right", padx=6)
        self.btn_cancel_edit = ttk.Button(actions, text="Annuler édition", command=self.controller.reset_form, state="disabled")
        self.btn_cancel_edit.pack(side="left")

        e_tva.bind("<KeyRelease>", lambda e: self.refresh_totals())

        self.refresh_totals()

    # ---------- Autocomplétion ----------
    def _update_suggestions(self, field):
        term = self.controller.var_c_nom.get().strip() if field=="nom" else self.controller.var_c_ent.get().strip()
        popup = self.popup_nom if field=="nom" else self.popup_ent
        if not term or len(term) < 2:
            popup.hide()
            return
        rows = search_clients(term, limit=20)
        self._suggest_map = {}
        items=[]
        for r in rows:
            label = self._format_client_label(r); items.append(label); self._suggest_map[label]=r
        popup.show(items)

    def _choose_suggestion(self, label):
        r = self._suggest_map.get(label)
        if r:
            self._fill_client_fields(r)

    @staticmethod
    def _format_client_label(r):
        nom = (r["nom"] or "").strip(); prenom = (r["prenom"] or "").strip()
        ent = (r["nom_entreprise"] or "").strip()
        left = ent if ent else f"{prenom} {nom}".strip()
        right = f"{prenom} {nom}".strip() if ent else ent
        middle = r["email"] or ""
        label = left
        if right: label += f" — {right}"
        if middle: label += f" — {middle}"
        return label

    def _fill_client_fields(self, r):
        self.controller.var_c_prenom.set(r["prenom"] or "")
        self.controller.var_c_nom.set(r["nom"] or "")
        self.controller.var_c_ent.set(r["nom_entreprise"] or "")
        self.controller.var_c_addr.set(r["adresse"] or "")
        self.controller.var_c_email.set(r["email"] or "")
        self.controller.var_c_tel.set(r["telephone"] or "")

    # ---------- Totaux live ----------
    def refresh_totals(self):
        subtotal = money(sum(i["total"] for i in self.items)) if self.items else 0.0
        try:
            tva_pct = float(self.controller.var_tva.get() or 0.0)
        except Exception:
            tva_pct = 0.0
        tva_amount = money(subtotal * (tva_pct/100.0))
        total = money(subtotal + tva_amount)
        self.lbl_ht.config(text=f"HT: {subtotal:.2f} {CURRENCY}")
        self.lbl_tva.config(text=f"TVA: {tva_amount:.2f} {CURRENCY}")
        self.lbl_ttc.config(text=f"TTC: {total:.2f} {CURRENCY}")

    # ---------- Articles ----------
    def _add_item(self):
        desc = self.var_i_desc.get().strip()
        if not desc:
            return messagebox.showwarning("Article","Saisis une description")
        try:
            qty = float(self.var_i_qty.get() or 1.0)
        except:
            return messagebox.showerror("Format","Quantité invalide")
        try:
            price = float(self.var_i_price.get() or 0.0)
        except:
            return messagebox.showerror("Format","Prix invalide")
        total = money(qty*price)
        it = {"description": desc, "qty": qty, "price": price, "total": total}
        self.items.append(it)
        self.tree.insert("", "end", values=(
            desc, f"{qty:.2f}".rstrip('0').rstrip('.'), f"{price:.2f}", f"{total:.2f}"
        ))
        self.var_i_desc.set(""); self.var_i_qty.set("1"); self.var_i_price.set("0.00")
        self.refresh_totals()

    def _remove_selected_item(self):
        sel = self.tree.selection()
        if not sel: return
        idx = self.tree.index(sel[0]); self.tree.delete(sel[0])
        if 0 <= idx < len(self.items): self.items.pop(idx)
        self.refresh_totals()

    def clear_items_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    # ---------- Client save ----------
    def _save_client_only(self):
        prenom=self.controller.var_c_prenom.get().strip()
        nom=self.controller.var_c_nom.get().strip()
        ent=self.controller.var_c_ent.get().strip()
        addr=self.controller.var_c_addr.get().strip()
        email=self.controller.var_c_email.get().strip()
        tel=self.controller.var_c_tel.get().strip()
        if not (nom or ent):
            return messagebox.showerror("Client","Nom ou Entreprise requis.")
        cid = find_or_create_client(prenom, nom, ent, addr, email, tel)
        update_client(cid, prenom, nom, ent, addr or None, email or None, tel or None)
        messagebox.showinfo("Client","Client enregistré/mis à jour.")

    def _get_current_client_id(self):
        return find_or_create_client(
            self.controller.var_c_prenom.get().strip(),
            self.controller.var_c_nom.get().strip(),
            self.controller.var_c_ent.get().strip(),
            self.controller.var_c_addr.get().strip(),
            self.controller.var_c_email.get().strip(),
            self.controller.var_c_tel.get().strip()
        )

    def _collect_totals(self):
        subtotal = money(sum(i["total"] for i in self.items))
        try:
            tva_pct = float(self.controller.var_tva.get() or 0.0)
        except:
            tva_pct = 0.0
        tva_amount = money(subtotal * (tva_pct/100.0))
        total = money(subtotal + tva_amount)
        return subtotal, tva_amount, total

    # ---------- Création / édition ----------
    def _create_invoice(self):
        if not (self.controller.var_c_nom.get().strip() or self.controller.var_c_ent.get().strip()):
            return messagebox.showerror("Client","Nom ou Entreprise requis.")
        if not self.items:
            return messagebox.showerror("Articles","Ajoute au moins une ligne.")
        cid = self._get_current_client_id()
        facture_num = generate_invoice_number()
        date_str = datetime.now().strftime("%Y-%m-%d")
        subtotal, tva_amount, total = self._collect_totals()
        inv_id = insert_invoice(
            cid, facture_num, date_str, subtotal, tva_amount, total, self.controller.var_notes.get().strip(), self.items
        )
        pdf_path = os.path.join(PDF_FOLDER, f"facture_{facture_num}.pdf")

        from db import get_conn
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM clients WHERE id=?", (cid,))
        client_row = cur.fetchone()
        conn.close()

        inv_obj = {
            "facture_num": facture_num,
            "date": date_str,
            "subtotal": subtotal,
            "tva": tva_amount,
            "total": total,
            "notes": self.controller.var_notes.get().strip(),
            "tva_rate": float(self.controller.var_tva.get() or 0.0),
        }
        create_pdf(inv_obj, client_row, self.items, pdf_path)
        set_pdf_path(inv_id, pdf_path)

        if messagebox.askyesno("OK", f"Facture {facture_num} enregistrée. Ouvrir le PDF ?"):
            self.controller.open_path(pdf_path)
        self.controller.reset_form()

    def _tva_pct_from_values(self, subtotal, tva_amount):
        try:
            if subtotal and tva_amount:
                return f"{(float(tva_amount)/float(subtotal))*100:.2f}"
        except:
            pass
        return "0"

    def _save_edit(self):
        if self.controller.current_invoice_id is None:
            return
        if not self.items:
            return messagebox.showerror("Articles","Ajoute au moins une ligne.")
        cid = self._get_current_client_id()
        inv, _, _ = get_invoice_with_items(self.controller.current_invoice_id)
        date_str = inv["date"]  # garde la date d'origine
        subtotal, tva_amount, total = self._collect_totals()
        update_invoice(self.controller.current_invoice_id, cid, date_str, subtotal, tva_amount, total, self.controller.var_notes.get().strip(), self.items)
        # PDF
        pdf_path = os.path.join(PDF_FOLDER, f"facture_{inv['facture_num']}.pdf")
        from db import get_conn
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM clients WHERE id=?", (cid,))
        client_row = cur.fetchone()
        conn.close()
        inv_obj = {
            "facture_num": inv["facture_num"],
            "date": date_str,
            "subtotal": subtotal,
            "tva": tva_amount,
            "total": total,
            "notes": self.controller.var_notes.get().strip(),
            "tva_rate": float(self.controller.var_tva.get() or 0.0),
        }
        create_pdf(inv_obj, client_row, self.items, pdf_path)
        set_pdf_path(self.controller.current_invoice_id, pdf_path)
        messagebox.showinfo("Édition", "Facture mise à jour et PDF régénéré.")
        self.controller.reset_form()
