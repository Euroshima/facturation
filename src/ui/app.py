# src/ui/app.py
import os, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY, PDF_FOLDER
from core.db import money
from core.version import __version__, __app_name__
from core.updater import check_and_maybe_update, start_auto_update

from .tab_create import TabCreate
from .tab_search import TabSearch
from .tab_clients import TabClients


class App(ttk.Frame):
    """Contrôleur principal : Notebook et menu Aide avec vérification des mises à jour."""
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

        # --- Menu principal ---
        menubar = tk.Menu(master)
        master.config(menu=menubar)

        menu_aide = tk.Menu(menubar, tearoff=0)
        menu_aide.add_command(label="Vérifier les mises à jour", command=self.check_updates)
        menu_aide.add_separator()
        menu_aide.add_command(label=f"À propos de {__app_name__} v{__version__}", command=self.show_about)
        menubar.add_cascade(label="Aide", menu=menu_aide)

        # --- Notebook + onglets ---
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_create = TabCreate(nb, controller=self)
        nb.add(self.tab_create, text="Créer / Éditer facture")

        self.tab_search = TabSearch(nb, controller=self)
        nb.add(self.tab_search, text="Rechercher factures")

        self.tab_clients = TabClients(nb, controller=self)
        nb.add(self.tab_clients, text="Clients")

        # Vérifie et installe automatiquement une nouvelle version (exe Windows uniquement)
        start_auto_update(master)

    # -------- actions menu aide --------
    def check_updates(self):
        """Ouvre un dialogue si une nouvelle version GitHub est disponible et propose l'installation."""
        try:
            check_and_maybe_update(ask_user=True)
        except Exception as e:
            messagebox.showerror("Mise à jour", f"Impossible de vérifier les mises à jour.\n\n{e}")

    def show_about(self):
        messagebox.showinfo(
            "À propos",
            f"{__app_name__}\nVersion : {__version__}\n\nApplication de facturation simple en Tkinter."
        )

    # -------- utilitaires partagés (accessibles par les onglets) --------
    def money(self, x):
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

        if hasattr(self.tab_create, "btn_save"):
            self.tab_create.btn_save.config(state="normal")
        if hasattr(self.tab_create, "btn_update"):
            self.tab_create.btn_update.config(state="disabled")
        if hasattr(self.tab_create, "btn_cancel_edit"):
            self.tab_create.btn_cancel_edit.config(state="disabled")
