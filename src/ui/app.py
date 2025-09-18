import os, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY, PDF_FOLDER
from core.db import money
from .tab_create import TabCreate
from .tab_search import TabSearch
from .tab_clients import TabClients


class App(ttk.Frame):
    """Contrôleur principal : crée le Notebook + partage l’état/les utilitaires entre onglets."""
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True)

        # État partagé
        self.items = []                 # lignes articles courantes (onglet création)
        self.current_invoice_id = None  # id facture en cours d'édition ou None
        # Champs client (StringVar partagés entre onglets)
        self.var_c_prenom = tk.StringVar()
        self.var_c_nom = tk.StringVar()
        self.var_c_ent = tk.StringVar()
        self.var_c_addr = tk.StringVar()
        self.var_c_email = tk.StringVar()
        self.var_c_tel = tk.StringVar()
        self.var_tva = tk.StringVar(value="0")
        self.var_notes = tk.StringVar()

        # Notebook + onglets
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_create = TabCreate(nb, controller=self)
        nb.add(self.tab_create, text="Créer / Éditer facture")

        self.tab_search = TabSearch(nb, controller=self)
        nb.add(self.tab_search, text="Rechercher factures")

        self.tab_clients = TabClients(nb, controller=self)
        nb.add(self.tab_clients, text="Clients")

    # -------- utilitaires partagés (accessibles par les onglets) --------
    def money(self, x):  # juste un proxy si tu veux l'appeler côté onglets
        return money(x)

    def open_path(self, path):
        try:
            webbrowser.open(f"file://{os.path.abspath(path)}")
        except Exception as e:
            messagebox.showerror("Ouverture", f"Impossible d'ouvrir: {e}")

    def reset_form(self):
        """Remet le formulaire (onglet création) à zéro et rafraîchit les totaux."""
        for v in [
            self.var_c_prenom, self.var_c_nom, self.var_c_ent, self.var_c_addr,
            self.var_c_email, self.var_c_tel, self.var_notes
        ]:
            v.set("")
        self.var_tva.set("0")
        self.items.clear()
        self.current_invoice_id = None
        if hasattr(self.tab_create, "clear_items_table"):
            self.tab_create.clear_items_table()
        if hasattr(self.tab_create, "refresh_totals"):
            self.tab_create.refresh_totals()
        # Réactive les bons boutons si l’onglet création a été construit
        if hasattr(self.tab_create, "btn_save"):
            self.tab_create.btn_save.config(state="normal")
        if hasattr(self.tab_create, "btn_update"):
            self.tab_create.btn_update.config(state="disabled")
        if hasattr(self.tab_create, "btn_cancel_edit"):
            self.tab_create.btn_cancel_edit.config(state="disabled")
