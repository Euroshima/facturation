import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY
from core.paths import invoice_pdf_path
from core.db import (
    money,
    find_or_create_client,
    generate_invoice_number,
    insert_invoice,
    update_invoice,
    set_pdf_path,
    get_invoice_with_items,
    search_clients,
    get_conn,
)
from pdf.pdfgen import create_pdf
from .send_email_dialog import show_send_email_dialog, invoice_email_context
from .widgets import SuggestPopup
import psycopg2.extras
from datetime import datetime

class TabCreate(ttk.Frame):
    """Onglet Création/Édition"""
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.items = []  # <-- AJOUTÉ
        self.lbl_ht = None
        self.lbl_tva = None
        self.lbl_ttc = None
        self.current_invoice_id = None
        self._build_ui()
        self.refresh_totals()

    # ----------------- Construction UI -----------------
    def _build_ui(self):
        # Bloc client
        client_fr = ttk.LabelFrame(self, text="Client")
        client_fr.pack(fill="x", padx=6, pady=6)

        r = 0
        ttk.Label(client_fr, text="Rechercher un client").grid(row=r, column=0, sticky="w")
        self.var_client_lookup = tk.StringVar()
        self.e_client_lookup = ttk.Entry(client_fr, textvariable=self.var_client_lookup, width=40)
        self.e_client_lookup.grid(row=r, column=1, columnspan=3, sticky="we", padx=4, pady=2)
        ttk.Label(client_fr, text="(nom, prénom ou entreprise — les champs se remplissent seuls)",
                  foreground="#666").grid(row=r, column=4, columnspan=2, sticky="w", padx=4)
        self._suggest = SuggestPopup(self.e_client_lookup, self._apply_client_suggestion)
        self._suggest_after = None
        self.e_client_lookup.bind("<KeyRelease>", self._on_client_lookup_key)
        self.e_client_lookup.bind("<Down>", lambda e: self._suggest.focus_list())
        self.e_client_lookup.bind("<Escape>", lambda e: self._suggest.hide())
        self.e_client_lookup.bind("<FocusOut>", lambda e: self.after(200, self._hide_suggest_if_unfocused))

        r += 1
        ttk.Label(client_fr, text="Prénom").grid(row=r, column=0, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_prenom, width=20).grid(row=r, column=1, padx=4, pady=2)
        ttk.Label(client_fr, text="Nom").grid(row=r, column=2, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_nom, width=20).grid(row=r, column=3, padx=4, pady=2)
        ttk.Label(client_fr, text="Entreprise").grid(row=r, column=4, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_ent, width=28).grid(row=r, column=5, padx=4, pady=2)

        r += 1
        ttk.Label(client_fr, text="Adresse (lignes séparées par \\n)").grid(row=r, column=0, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_addr, width=70).grid(row=r, column=1, columnspan=5, sticky="we", padx=4, pady=2)

        r += 1
        ttk.Label(client_fr, text="Email").grid(row=r, column=0, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_email, width=25).grid(row=r, column=1, padx=4, pady=2)
        ttk.Label(client_fr, text="Téléphone").grid(row=r, column=2, sticky="w")
        ttk.Entry(client_fr, textvariable=self.controller.var_c_tel, width=20).grid(row=r, column=3, padx=4, pady=2)
        for i in range(6):
            client_fr.columnconfigure(i, weight=1)

        # Bloc articles
        items_fr = ttk.LabelFrame(self, text="Articles")
        items_fr.pack(fill="both", padx=6, pady=6, expand=True)
        self.var_i_desc = tk.StringVar()
        self.var_i_qty = tk.StringVar(value="1")
        self.var_i_price = tk.StringVar(value="0.00")
        self.var_i_unit = tk.StringVar(value="kg")  # unité par défaut

        top_labels = ttk.Frame(items_fr)
        top_labels.pack(fill="x", padx=4, pady=(4,0))
        ttk.Label(top_labels, text="Description", width=60, anchor="w").pack(side="left", padx=4)
        ttk.Label(top_labels, text="Quantité", width=8, anchor="e").pack(side="left", padx=4)
        ttk.Label(top_labels, text="Unité", width=8, anchor="center").pack(side="left", padx=4)
        ttk.Label(top_labels, text=f"Prix unit. ({CURRENCY})", width=12, anchor="e").pack(side="left", padx=4)

        top = ttk.Frame(items_fr)
        top.pack(fill="x", padx=4, pady=2)
        ttk.Entry(top, textvariable=self.var_i_desc, width=60).pack(side="left", padx=4)
        ttk.Entry(top, textvariable=self.var_i_qty, width=8).pack(side="left", padx=4)
        ttk.Combobox(top, textvariable=self.var_i_unit, values=["kg","unité"], width=8, state="readonly").pack(side="left", padx=4)
        ttk.Entry(top, textvariable=self.var_i_price, width=12).pack(side="left", padx=4)
        ttk.Button(top, text="Ajouter", command=self.add_item).pack(side="left", padx=4)
        ttk.Button(top, text="Supprimer sélection", command=self.remove_selected_item).pack(side="left", padx=4)

        self.tree = ttk.Treeview(items_fr, columns=("desc", "qty", "unit", "price", "total"), show="headings", height=8)
        self.tree.heading("desc", text="Description")
        self.tree.heading("qty", text="Qté")
        self.tree.heading("unit", text="Unité")
        self.tree.heading("price", text=f"Prix unit. ({CURRENCY})")
        self.tree.heading("total", text=f"Total ({CURRENCY})")
        self.tree.column("desc", width=400)
        self.tree.column("qty", width=60, anchor="e")
        self.tree.column("unit", width=60, anchor="center")
        self.tree.column("price", width=120, anchor="e")
        self.tree.column("total", width=120, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.bind("<Double-1>", self._edit_selected_item)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=6, pady=6)
        left = ttk.Frame(bottom)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="TVA (%)").pack(side="left")
        e_tva = ttk.Entry(left, textvariable=self.controller.var_tva, width=8)
        e_tva.pack(side="left", padx=4)
        e_tva.bind("<KeyRelease>", lambda e: self.refresh_totals())
        ttk.Label(left, text="Notes").pack(side="left")
        ttk.Entry(left, textvariable=self.controller.var_notes, width=50).pack(side="left", padx=4)

        right = ttk.Frame(bottom)
        right.pack(side="right")
        self.lbl_ht = ttk.Label(right, text=f"HT: 0.00 {CURRENCY}")
        self.lbl_tva = ttk.Label(right, text=f"TVA: 0.00 {CURRENCY}")
        self.lbl_ttc = ttk.Label(right, text=f"TTC: 0.00 {CURRENCY}", font=("TkDefaultFont", 10, "bold"))
        self.lbl_ht.grid(row=0, column=0, sticky="e", padx=8)
        self.lbl_tva.grid(row=1, column=0, sticky="e", padx=8)
        self.lbl_ttc.grid(row=2, column=0, sticky="e", padx=8)

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=6, pady=6)
        self.btn_save = ttk.Button(actions, text="Générer PDF & Enregistrer (NOUVELLE facture)", command=self.create_invoice)
        self.btn_save.pack(side="right")
        self.btn_save_send = ttk.Button(actions, text="Générer PDF, Enregistrer & Envoyer par e-mail", command=self.create_invoice_and_email)
        self.btn_save_send.pack(side="right", padx=6)
        self.btn_update = ttk.Button(actions, text="Enregistrer modifications (facture existante)", command=self.save_edit, state="disabled")
        self.btn_update.pack(side="right", padx=6)
        self.btn_cancel_edit = ttk.Button(actions, text="Annuler édition", command=self.clear_all, state="disabled")
        self.btn_cancel_edit.pack(side="left")
        ttk.Button(actions, text="Tout effacer", command=self.clear_all).pack(side="left", padx=6)

    # ----------------- Recherche client -----------------
    def _on_client_lookup_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        # Frappe rapide : on ne requête la base qu'après une courte pause.
        if self._suggest_after:
            self.after_cancel(self._suggest_after)
        self._suggest_after = self.after(300, self._run_client_lookup)

    def _run_client_lookup(self):
        self._suggest_after = None
        term = self.var_client_lookup.get().strip()
        if len(term) < 2:
            return self._suggest.hide()
        try:
            rows = search_clients(term, limit=10)
        except Exception:
            return self._suggest.hide()
        self._suggest.show([(self._client_label(r), r) for r in rows])

    @staticmethod
    def _client_label(row):
        nom = f"{(row.get('prenom') or '').strip()} {(row.get('nom') or '').strip()}".strip()
        ent = (row.get("nom_entreprise") or "").strip()
        contact = (row.get("email") or "").strip() or (row.get("telephone") or "").strip()
        label = " — ".join(p for p in (ent, nom) if p) or "(client sans nom)"
        return f"{label} · {contact}" if contact else label

    def _apply_client_suggestion(self, row):
        self.controller.var_c_prenom.set(row.get("prenom") or "")
        self.controller.var_c_nom.set(row.get("nom") or "")
        self.controller.var_c_ent.set(row.get("nom_entreprise") or "")
        self.controller.var_c_addr.set(row.get("adresse") or "")
        self.controller.var_c_email.set(row.get("email") or "")
        self.controller.var_c_tel.set(row.get("telephone") or "")
        self.var_client_lookup.set(self._client_label(row))
        self.e_client_lookup.focus_set()

    def _hide_suggest_if_unfocused(self):
        """Ferme la liste sauf si le focus vient d'y passer (clic sur une ligne)."""
        if self.focus_get() is not self._suggest.listbox:
            self._suggest.hide()

    # ----------------- Gestion articles -----------------
    def add_item(self):
        desc = self.var_i_desc.get().strip()
        if not desc:
            return messagebox.showwarning("Article", "Saisis une description")
        try:
            qty = float(self.var_i_qty.get() or 1.0)
            price = float(self.var_i_price.get() or 0.0)
        except Exception:
            return messagebox.showerror("Format", "Quantité ou prix invalide")
        unit = self.var_i_unit.get() or "kg"
        total = money(qty * price)
        item = {"description": desc, "qty": qty, "unit": unit, "price": price, "total": total}
        self.items.append(item)
        self.tree.insert(
            "", "end",
            values=(desc, f"{qty:.2f}".rstrip("0").rstrip("."), unit, f"{price:.2f}", f"{total:.2f}")
        )
        self.var_i_desc.set("")
        self.var_i_qty.set("1")
        self.var_i_unit.set("kg")
        self.var_i_price.set("0.00")
        self.refresh_totals()

    def remove_selected_item(self):
        sel = self.tree.selection()
        if not sel: return
        idx = self.tree.index(sel[0])
        self.tree.delete(sel[0])
        if 0 <= idx < len(self.items):
            self.items.pop(idx)
        self.refresh_totals()

    def _edit_selected_item(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        item_data = self.items[idx]

        modal = tk.Toplevel(self)
        modal.title("Modifier l'article")
        modal.transient(self)
        modal.grab_set()

        ttk.Label(modal, text="Description").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        e_desc = ttk.Entry(modal, width=50)
        e_desc.grid(row=0, column=1, padx=4, pady=4)
        e_desc.insert(0, item_data.get("description", ""))

        ttk.Label(modal, text="Quantité").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        e_qty = ttk.Entry(modal, width=20)
        e_qty.grid(row=1, column=1, padx=4, pady=4)
        e_qty.insert(0, str(item_data.get("qty", 1)))

        ttk.Label(modal, text="Unité").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        e_unit = ttk.Combobox(modal, values=["kg","unité"], state="readonly", width=18)
        e_unit.grid(row=2, column=1, padx=4, pady=4)
        e_unit.set(item_data.get("unit", "kg"))

        ttk.Label(modal, text=f"Prix unit. ({CURRENCY})").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        e_price = ttk.Entry(modal, width=20)
        e_price.grid(row=3, column=1, padx=4, pady=4)
        e_price.insert(0, str(item_data.get("price", 0.0)))

        def save_changes():
            try:
                qty_val = float(e_qty.get() or 1.0)
                price_val = float(e_price.get() or 0.0)
            except Exception:
                return messagebox.showerror("Erreur", "Quantité ou prix invalide")
            unit_val = e_unit.get() or "kg"
            desc_val = e_desc.get().strip() or "Article"
            total_val = money(qty_val * price_val)

            self.items[idx] = {
                "description": desc_val,
                "qty": qty_val,
                "unit": unit_val,
                "price": price_val,
                "total": total_val
            }

            self.tree.item(sel[0], values=(desc_val, f"{qty_val:.2f}".rstrip("0").rstrip("."), unit_val, f"{price_val:.2f}", f"{total_val:.2f}"))
            self.refresh_totals()
            modal.destroy()

        ttk.Button(modal, text="Enregistrer", command=save_changes).grid(row=4, column=0, columnspan=2, pady=10)
        modal.wait_window(modal)

    # ----------------- Totaux -----------------
    def refresh_totals(self):
        subtotal = money(sum(i["total"] for i in self.items)) if self.items else 0.0
        try:
            tva_pct = float(self.controller.var_tva.get() or 0.0)
        except Exception:
            tva_pct = 0.0
        tva_amount = money(subtotal * (tva_pct / 100.0))
        total = money(subtotal + tva_amount)
        if self.lbl_ht and self.lbl_tva and self.lbl_ttc:
            self.lbl_ht.config(text=f"HT: {subtotal:.2f} {CURRENCY}")
            self.lbl_tva.config(text=f"TVA: {tva_amount:.2f} {CURRENCY}")
            self.lbl_ttc.config(text=f"TTC: {total:.2f} {CURRENCY}")

    def _collect_totals(self):
        subtotal = money(sum(i["total"] for i in self.items))
        try:
            tva_pct = float(self.controller.var_tva.get() or 0.0)
        except Exception:
            tva_pct = 0.0
        tva_amount = money(subtotal * (tva_pct / 100.0))
        total = money(subtotal + tva_amount)
        return subtotal, tva_amount, total

    # ----------------- Client -----------------
    def _get_current_client_id(self):
        return find_or_create_client(
            self.controller.var_c_prenom.get().strip(),
            self.controller.var_c_nom.get().strip(),
            self.controller.var_c_ent.get().strip(),
            self.controller.var_c_addr.get().strip(),
            self.controller.var_c_email.get().strip(),
            self.controller.var_c_tel.get().strip(),
        )

    # ----------------- Création nouvelle facture -----------------
    def _form_is_valid(self) -> bool:
        if not (self.controller.var_c_nom.get().strip() or self.controller.var_c_ent.get().strip()):
            messagebox.showerror("Client", "Nom ou Entreprise requis pour créer une facture.")
            return False
        if not self.items:
            messagebox.showerror("Articles", "Ajoute au moins une ligne.")
            return False
        return True

    def _save_new_invoice(self):
        """Enregistre la facture en base et génère son PDF.
        Retourne (inv_obj, client_row, pdf_path)."""
        cid = self._get_current_client_id()
        facture_num = generate_invoice_number()
        date_str = datetime.now().strftime("%Y-%m-%d")
        subtotal, tva_amount, total = self._collect_totals()
        inv_id = insert_invoice(cid, facture_num, date_str, subtotal, tva_amount, total, self.controller.var_notes.get().strip(), self.items)

        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM clients WHERE id=%s", (cid,))
        client_row = cur.fetchone()
        conn.close()

        pdf_path = invoice_pdf_path(client_row, facture_num)

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
        return inv_obj, client_row, pdf_path

    def create_invoice(self):
        if not self._form_is_valid():
            return
        try:
            inv_obj, _, pdf_path = self._save_new_invoice()
        except Exception as e:
            return messagebox.showerror("Erreur", f"Impossible de créer la facture :\n{e}")

        if messagebox.askyesno("Facture créée", f"Facture {inv_obj['facture_num']} enregistrée.\nOuvrir le PDF ?"):
            self.controller.open_path(pdf_path)
        self.clear_all()

    def create_invoice_and_email(self):
        """Génère le PDF, enregistre la facture, puis ouvre la fenêtre d'envoi."""
        if not self._form_is_valid():
            return
        try:
            inv_obj, client_row, pdf_path = self._save_new_invoice()
        except Exception as e:
            return messagebox.showerror("Erreur", f"Impossible de créer la facture :\n{e}")

        show_send_email_dialog(
            self.winfo_toplevel(),
            facture_num=inv_obj["facture_num"],
            to_addr=(client_row or {}).get("email", ""),
            pdf_path=pdf_path,
            context=invoice_email_context(inv_obj, client_row),
        )
        self.clear_all()

    # ----------------- Sauvegarder modifications facture -----------------
    def save_edit(self):
        if not self.current_invoice_id:
            return messagebox.showwarning("Modifier", "Aucune facture en édition")
        if not self.items:
            return messagebox.showerror("Articles", "Ajoute au moins une ligne")
        try:
            cid = self._get_current_client_id()
            subtotal, tva_amount, total = self._collect_totals()

            inv, _, _ = get_invoice_with_items(self.current_invoice_id)
            if not inv:
                return messagebox.showerror("Modifier", "Facture introuvable en base.")
            original_date = inv["date"]
            facture_num = inv["facture_num"]

            update_invoice(
                self.current_invoice_id,
                cid,
                original_date,
                subtotal,
                tva_amount,
                total,
                self.controller.var_notes.get().strip(),
                self.items
            )

            conn = get_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT * FROM clients WHERE id=%s", (cid,))
            client_row = cur.fetchone()
            conn.close()

            pdf_path = invoice_pdf_path(client_row, facture_num)

            inv_obj = {
                "facture_num": facture_num,
                "date": original_date,
                "subtotal": subtotal,
                "tva": tva_amount,
                "total": total,
                "notes": self.controller.var_notes.get().strip(),
                "tva_rate": float(self.controller.var_tva.get() or 0.0),
            }

            create_pdf(inv_obj, client_row, self.items, pdf_path)
            set_pdf_path(self.current_invoice_id, pdf_path)

            messagebox.showinfo("Modification", f"Facture {facture_num} mise à jour.")
            self.clear_all()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder la facture :\n{e}")

    # ----------------- Charger facture existante -----------------
    def load_invoice_for_edit(self, invoice_id, client_data, items, tva, notes):
        self.clear_all()
        self.current_invoice_id = invoice_id
        self.btn_update.config(state="normal")
        self.btn_cancel_edit.config(state="normal")

        self.controller.var_c_prenom.set(client_data.get("prenom",""))
        self.controller.var_c_nom.set(client_data.get("nom",""))
        self.controller.var_c_ent.set(client_data.get("entreprise",""))
        self.controller.var_c_addr.set(client_data.get("adresse",""))
        self.controller.var_c_email.set(client_data.get("email",""))
        self.controller.var_c_tel.set(client_data.get("tel",""))

        self.controller.var_tva.set(str(tva))
        self.controller.var_notes.set(notes)

        for item in items:
            self.items.append(item)
            total = money(item["qty"]*item["price"])
            self.tree.insert("", "end", values=(
                item["description"],
                f"{item['qty']:.2f}".rstrip("0").rstrip("."),
                item["unit"],
                f"{item['price']:.2f}",
                f"{total:.2f}"
            ))
        self.refresh_totals()

    # ----------------- Tout effacer -----------------
    def clear_all(self):
        self.current_invoice_id = None
        self.btn_update.config(state="disabled")
        self.btn_cancel_edit.config(state="disabled")

        self.controller.var_c_prenom.set("")
        self.controller.var_c_nom.set("")
        self.controller.var_c_ent.set("")
        self.controller.var_c_addr.set("")
        self.controller.var_c_email.set("")
        self.controller.var_c_tel.set("")
        self.controller.var_tva.set("0")
        self.controller.var_notes.set("")
        self.var_client_lookup.set("")
        self._suggest.hide()

        self.var_i_desc.set("")
        self.var_i_qty.set("1")
        self.var_i_unit.set("kg")
        self.var_i_price.set("0.00")

        self.clear_items_table()
        self.items.clear()
        self.refresh_totals()

    # ----------------- Vider table des articles -----------------
    def clear_items_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
