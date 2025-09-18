# src/ui/tab_create.py
import os
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY, PDF_FOLDER
from core.db import (
    money,
    find_or_create_client,
    generate_invoice_number,
    insert_invoice,
    set_pdf_path,
    get_conn,
)
from pdf.pdfgen import create_pdf


class TabCreate(ttk.Frame):
    """
    Onglet Création/Édition. Utilise l’état partagé exposé par le controller (App):
      - controller.items (list[dict]) : lignes d’articles
      - controller.var_c_* (StringVar) : champs client
      - controller.var_tva / controller.var_notes
      - controller.reset_form(), controller.open_path()
    """

    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()
        self.refresh_totals()

    # ---------------- UI ----------------
    def _build_ui(self):
        # Bloc client
        client_fr = ttk.LabelFrame(self, text="Client")
        client_fr.pack(fill="x", padx=6, pady=6)

        r = 0
        ttk.Label(client_fr, text="Prénom").grid(row=r, column=0, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_prenom, width=20).grid(
            row=r, column=1, padx=4, pady=2
        )
        ttk.Label(client_fr, text="Nom").grid(row=r, column=2, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_nom, width=20).grid(
            row=r, column=3, padx=4, pady=2
        )
        ttk.Label(client_fr, text="Entreprise").grid(row=r, column=4, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_ent, width=28).grid(
            row=r, column=5, padx=4, pady=2
        )

        r += 1
        ttk.Label(client_fr, text="Adresse (lignes séparées par \\n)").grid(
            row=r, column=0, sticky="w"
        )
        ttk.Entry(client_fr, textvariable=self.controller.var_c_addr, width=70).grid(
            row=r, column=1, columnspan=5, sticky="we", padx=4, pady=2
        )

        r += 1
        ttk.Label(client_fr, text="Email").grid(row=r, column=0, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_email, width=25).grid(
            row=r, column=1, padx=4, pady=2
        )
        ttk.Label(client_fr, text="Téléphone").grid(row=r, column=2, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_tel, width=20).grid(
            row=r, column=3, padx=4, pady=2
        )
        for i in range(6):
            client_fr.columnconfigure(i, weight=1)

        # Bloc articles
        items_fr = ttk.LabelFrame(self, text="Articles")
        items_fr.pack(fill="both", padx=6, pady=6, expand=True)

        self.var_i_desc = tk.StringVar()
        self.var_i_qty = tk.StringVar(value="1")
        self.var_i_price = tk.StringVar(value="0.00")

        top = ttk.Frame(items_fr)
        top.pack(fill="x", padx=4, pady=4)
        ttk.Entry(top, textvariable=self.var_i_desc, width=60).pack(side="left", padx=4)
        ttk.Entry(top, textvariable=self.var_i_qty, width=8).pack(side="left", padx=4)
        ttk.Entry(top, textvariable=self.var_i_price, width=12).pack(side="left", padx=4)
        ttk.Button(top, text="Ajouter", command=self.add_item).pack(side="left", padx=4)
        ttk.Button(
            top, text="Supprimer sélection", command=self.remove_selected_item
        ).pack(side="left", padx=4)

        self.tree = ttk.Treeview(
            items_fr, columns=("desc", "qty", "price", "total"), show="headings", height=8
        )
        self.tree.heading("desc", text="Description")
        self.tree.heading("qty", text="Qté")
        self.tree.heading("price", text=f"Prix unit. ({CURRENCY})")
        self.tree.heading("total", text=f"Total ({CURRENCY})")
        self.tree.column("desc", width=500)
        self.tree.column("qty", width=60, anchor="e")
        self.tree.column("price", width=120, anchor="e")
        self.tree.column("total", width=120, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Totaux + notes
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=6, pady=6)

        left = ttk.Frame(bottom)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="TVA (%)").pack(side="left")
        e_tva = ttk.Entry(left, textvariable=self.controller.var_tva, width=8)
        e_tva.pack(side="left", padx=4)
        e_tva.bind("<KeyRelease>", lambda e: self.refresh_totals())

        ttk.Label(left, text="Notes").pack(side="left")
        ttk.Entry(left, textvariable=self.controller.var_notes, width=50).pack(
            side="left", padx=4
        )

        right = ttk.Frame(bottom)
        right.pack(side="right")
        self.lbl_ht = ttk.Label(right, text=f"HT: 0.00 {CURRENCY}")
        self.lbl_tva = ttk.Label(right, text=f"TVA: 0.00 {CURRENCY}")
        self.lbl_ttc = ttk.Label(
            right, text=f"TTC: 0.00 {CURRENCY}", font=("TkDefaultFont", 10, "bold")
        )
        self.lbl_ht.grid(row=0, column=0, sticky="e", padx=8)
        self.lbl_tva.grid(row=1, column=0, sticky="e", padx=8)
        self.lbl_ttc.grid(row=2, column=0, sticky="e", padx=8)

        # Actions
        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=6, pady=6)
        self.btn_save = ttk.Button(
            actions,
            text="Générer PDF & Enregistrer (NOUVELLE facture)",
            command=self.create_invoice,  # <-- branchement du bouton
        )
        self.btn_save.pack(side="right")

        # Boutons d’édition (activés par App quand on charge une facture)
        self.btn_update = ttk.Button(
            actions,
            text="Enregistrer modifications (facture existante)",
            command=getattr(self, "save_edit", lambda: None),
            state="disabled",
        )
        self.btn_update.pack(side="right", padx=6)
        self.btn_cancel_edit = ttk.Button(
            actions,
            text="Annuler édition",
            command=getattr(self.controller, "reset_form", lambda: None),
            state="disabled",
        )
        self.btn_cancel_edit.pack(side="left")

    # ------------- Articles -------------
    def add_item(self):
        desc = self.var_i_desc.get().strip()
        if not desc:
            return messagebox.showwarning("Article", "Saisis une description")
        try:
            qty = float(self.var_i_qty.get() or 1.0)
        except Exception:
            return messagebox.showerror("Format", "Quantité invalide")
        try:
            price = float(self.var_i_price.get() or 0.0)
        except Exception:
            return messagebox.showerror("Format", "Prix invalide")

        total = money(qty * price)
        item = {"description": desc, "qty": qty, "price": price, "total": total}
        self.controller.items.append(item)
        self.tree.insert(
            "", "end",
            values=(
                desc,
                f"{qty:.2f}".rstrip("0").rstrip("."),
                f"{price:.2f}",
                f"{total:.2f}",
            ),
        )
        self.var_i_desc.set("")
        self.var_i_qty.set("1")
        self.var_i_price.set("0.00")
        self.refresh_totals()

    def remove_selected_item(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self.tree.delete(sel[0])
        if 0 <= idx < len(self.controller.items):
            self.controller.items.pop(idx)
        self.refresh_totals()

    def clear_items_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    # ------------- Totaux -------------
    def refresh_totals(self):
        subtotal = money(sum(i["total"] for i in self.controller.items)) if self.controller.items else 0.0
        try:
            tva_pct = float(self.controller.var_tva.get() or 0.0)
        except Exception:
            tva_pct = 0.0
        tva_amount = money(subtotal * (tva_pct / 100.0))
        total = money(subtotal + tva_amount)
        self.lbl_ht.config(text=f"HT: {subtotal:.2f} {CURRENCY}")
        self.lbl_tva.config(text=f"TVA: {tva_amount:.2f} {CURRENCY}")
        self.lbl_ttc.config(text=f"TTC: {total:.2f} {CURRENCY}")

    # ------------- Création -------------
    def _collect_totals(self):
        subtotal = money(sum(i["total"] for i in self.controller.items))
        try:
            tva_pct = float(self.controller.var_tva.get() or 0.0)
        except Exception:
            tva_pct = 0.0
        tva_amount = money(subtotal * (tva_pct / 100.0))
        total = money(subtotal + tva_amount)
        return subtotal, tva_amount, total

    def _get_current_client_id(self):
        return find_or_create_client(
            self.controller.var_c_prenom.get().strip(),
            self.controller.var_c_nom.get().strip(),
            self.controller.var_c_ent.get().strip(),
            self.controller.var_c_addr.get().strip(),
            self.controller.var_c_email.get().strip(),
            self.controller.var_c_tel.get().strip(),
        )

    def create_invoice(self):
        """Génère le PDF et enregistre la NOUVELLE facture en DB."""
        # validations
        if not (
            self.controller.var_c_nom.get().strip()
            or self.controller.var_c_ent.get().strip()
        ):
            return messagebox.showerror(
                "Client", "Nom ou Entreprise requis pour créer une facture."
            )
        if not self.controller.items:
            return messagebox.showerror("Articles", "Ajoute au moins une ligne.")

        try:
            cid = self._get_current_client_id()
            facture_num = generate_invoice_number()
            from datetime import datetime

            date_str = datetime.now().strftime("%Y-%m-%d")
            subtotal, tva_amount, total = self._collect_totals()

            # insertion DB (facture + items)
            inv_id = insert_invoice(
                cid,
                facture_num,
                date_str,
                subtotal,
                tva_amount,
                total,
                self.controller.var_notes.get().strip(),
                self.controller.items,
            )

            # PDF
            os.makedirs(PDF_FOLDER, exist_ok=True)
            pdf_path = os.path.join(PDF_FOLDER, f"facture_{facture_num}.pdf")

            # client complet
            conn = get_conn()
            cur = conn.cursor()
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

            try:
                create_pdf(inv_obj, client_row, self.controller.items, pdf_path)
                set_pdf_path(inv_id, pdf_path)
            except Exception as e:
                messagebox.showerror("PDF", f"Impossible de générer le PDF :\n{e}")
                return

            if messagebox.askyesno(
                "Facture créée",
                f"Facture {facture_num} enregistrée.\nOuvrir le PDF ?",
            ):
                self.controller.open_path(pdf_path)

            # reset du formulaire
            self.controller.reset_form()

        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Impossible de créer la facture :\n{e}",
            )
