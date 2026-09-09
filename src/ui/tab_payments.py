import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY, MY_INFO
from core.db import list_invoices_by_payment, mark_invoices_paid, mark_invoices_unpaid
from pdf.pdfgen import _parse_date, _fmt_date
from .widgets import make_sortable
from .invoice_actions import regenerate_pdf
from .send_email_dialog import show_send_email_dialog, invoice_email_context


def _echeance(date_str):
    """Date d'échéance = date de facture + délai de paiement de l'entreprise."""
    d = _parse_date(date_str)
    if not d:
        return None
    try:
        delai = int(MY_INFO.get("delai_paiement_jours", 30))
    except (TypeError, ValueError):
        delai = 30
    return d + datetime.timedelta(days=delai)


class TabPayments(ttk.Frame):
    """Onglet Paiements : impayés en tête, marquage rapide comme réglé."""

    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)

        ttk.Button(bar, text="Marquer payée", command=self._mark_paid).pack(side="left")
        ttk.Button(bar, text="Marquer non payée", command=self._mark_unpaid).pack(side="left", padx=6)
        ttk.Button(bar, text="Relancer par e-mail", command=self._relance_selected).pack(side="left")
        ttk.Button(bar, text="Rafraîchir", command=self.refresh).pack(side="left", padx=6)

        self.var_show_paid = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Afficher aussi les payées",
                        variable=self.var_show_paid,
                        command=self.refresh).pack(side="left", padx=12)

        self.tree = ttk.Treeview(
            self,
            columns=("id", "num", "date", "client", "total", "echeance", "retard", "paid"),
            show="headings", height=14, selectmode="extended"
        )
        for col, title, w, anchor in [
            ("id", "ID", 60, "center"),
            ("num", "N° Facture", 140, "w"),
            ("date", "Date", 100, "center"),
            ("client", "Client", 240, "w"),
            ("total", f"Total ({CURRENCY})", 120, "e"),
            ("echeance", "Échéance", 100, "center"),
            ("retard", "Retard (j)", 90, "e"),
            ("paid", "Payée le", 100, "center"),
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=w, anchor=anchor)
        make_sortable(self.tree, numeric_columns=("id", "total", "retard"))
        self.tree.tag_configure("retard", foreground="#b63410")
        self.tree.tag_configure("payee", foreground="#777")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Double-1>", lambda e: self._mark_paid())

        self.lbl_total = ttk.Label(self, text="", anchor="e",
                                   font=("TkDefaultFont", 10, "bold"))
        self.lbl_total.pack(fill="x", padx=10, pady=(0, 8))

    # ---- Données ----
    def refresh(self):
        try:
            rows = list_invoices_by_payment(self.var_show_paid.get())
        except Exception as e:
            return messagebox.showerror("Paiements", f"Lecture impossible :\n{e}")

        for i in self.tree.get_children():
            self.tree.delete(i)

        today = datetime.date.today()
        impayes_total = 0.0
        impayes_count = 0

        for r in rows:
            paid_at = r.get("paid_at")
            ech = _echeance(r.get("date"))
            retard = (today - ech).days if (ech and not paid_at and ech < today) else 0
            total = float(r.get("total") or 0.0)

            if not paid_at:
                impayes_total += total
                impayes_count += 1

            client_name = (r.get("nom_entreprise") or "").strip() or \
                f"{(r.get('prenom') or '').strip()} {(r.get('nom') or '').strip()}".strip()

            tags = ("payee",) if paid_at else (("retard",) if retard else ())
            self.tree.insert("", "end", tags=tags, values=(
                r.get("id"),
                r.get("facture_num"),
                _fmt_date(r.get("date")),
                client_name,
                f"{total:.2f}",
                _fmt_date(ech.isoformat()) if ech else "",
                retard or "",
                _fmt_date(paid_at) if paid_at else "",
            ))
        self.tree.reapply_sort()
        self.lbl_total.config(
            text=f"Impayés : {impayes_count} facture(s) — {impayes_total:.2f} {CURRENCY}"
        )

    # ---- Actions ----
    def _selected_ids(self, action):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Paiements", f"Sélectionne au moins une facture à {action}.")
            return []
        return [self.tree.item(iid, "values")[0] for iid in sel]

    def _mark_paid(self):
        ids = self._selected_ids("marquer payée")
        if not ids:
            return
        try:
            mark_invoices_paid(ids)
        except Exception as e:
            return messagebox.showerror("Paiements", f"Échec de l'enregistrement :\n{e}")
        self.refresh()

    def _relance_selected(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("Relance", "Sélectionne la facture à relancer.")
        inv_id = self.tree.item(sel[0], "values")[0]
        try:
            pdf_path, inv, client = regenerate_pdf(inv_id)
        except Exception as e:
            return messagebox.showerror("Relance", f"Impossible de préparer le PDF :\n{e}")
        if not pdf_path:
            return messagebox.showerror("Relance", "Facture introuvable en base.")

        show_send_email_dialog(
            self.winfo_toplevel(),
            facture_num=inv.get("facture_num"),
            to_addr=(client or {}).get("email", ""),
            pdf_path=pdf_path,
            context=invoice_email_context(inv, client),
            template="relance",
        )

    def _mark_unpaid(self):
        ids = self._selected_ids("remettre en impayée")
        if not ids:
            return
        try:
            mark_invoices_unpaid(ids)
        except Exception as e:
            return messagebox.showerror("Paiements", f"Échec de l'enregistrement :\n{e}")
        self.refresh()
