# src/ui/app.py
import os, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

from core.settings import CURRENCY, PDF_FOLDER
from core.db import money
from core.version import __version__, __app_name__
from core.updater import check_and_maybe_update, check_for_update_async
from core.changelog import load_changelog

from .tab_create import TabCreate
from .tab_search import TabSearch
from .tab_clients import TabClients
from .db_config_dialog import show_db_config_dialog
from .company_dialog import show_company_dialog
from .smtp_dialog import show_smtp_dialog
from .mail_template_dialog import show_mail_template_dialog


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

        menu_param = tk.Menu(menubar, tearoff=0)
        menu_param.add_command(label="Mon entreprise…", command=self.edit_company)
        menu_param.add_command(label="E-mail (SMTP)…", command=self.edit_smtp)
        menu_param.add_command(label="Modèle d'e-mail…", command=self.edit_mail_template)
        menu_param.add_separator()
        menu_param.add_command(label="Connexion à la base de données…", command=self.edit_db_config)
        menubar.add_cascade(label="Paramètres", menu=menu_param)

        menu_aide = tk.Menu(menubar, tearoff=0)
        menu_aide.add_command(label="Vérifier les mises à jour", command=self.check_updates)
        menu_aide.add_separator()
        menu_aide.add_command(label="Notes de version", command=self.show_changelog)
        menubar.add_cascade(label="Aide", menu=menu_aide)

        # --- Barre d'état (version en bas à gauche) : packée avant le notebook
        #     pour rester ancrée en bas même quand le notebook s'étend ---
        statusbar = ttk.Frame(self, relief="sunken")
        statusbar.pack(side="bottom", fill="x")
        ttk.Label(
            statusbar, text=f"{__app_name__}  v{__version__}", anchor="w", padding=(6, 2)
        ).pack(side="left")
        # Indicateur « mise à jour disponible » (bas à droite), masqué au départ
        self._update_notified = False
        self.lbl_update = tk.Label(
            statusbar, text="", fg="#b63410", cursor="hand2",
            font=("TkDefaultFont", 9, "bold"), padx=8,
        )
        self.lbl_update.pack(side="right")
        self.lbl_update.bind("<Button-1>", lambda e: self.check_updates())

        # --- Notebook + onglets ---
        nb = ttk.Notebook(self)
        nb.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        self.tab_create = TabCreate(nb, controller=self)
        nb.add(self.tab_create, text="Créer / Éditer facture")

        self.tab_search = TabSearch(nb, controller=self)
        nb.add(self.tab_search, text="Rechercher factures")

        self.tab_clients = TabClients(nb, controller=self)
        nb.add(self.tab_clients, text="Clients")

        # Vérification NON bloquante : on ne fait que *signaler* si une version
        # plus récente existe (indicateur + petit pop-up). Le remplacement
        # d'exe ne se déclenche que si l'utilisateur clique.
        check_for_update_async(
            lambda v: self.after(0, lambda: self._notify_update_available(v))
        )

    # -------- mise à jour : signalement --------
    def _notify_update_available(self, version):
        try:
            self.lbl_update.config(text=f"⬆  Mise à jour v{version} disponible")
        except Exception:
            pass
        if self._update_notified:
            return
        self._update_notified = True
        if messagebox.askyesno(
            "Mise à jour disponible",
            f"La version {version} est disponible "
            f"(vous utilisez la v{__version__}).\n\nL'installer maintenant ?",
        ):
            try:
                check_and_maybe_update(ask_user=False, show_errors=True)
            except Exception as e:
                messagebox.showerror("Mise à jour", f"Échec :\n{e}")

    # -------- actions menu --------
    def edit_company(self):
        if show_company_dialog(self.winfo_toplevel()):
            messagebox.showinfo("Paramètres",
                                "Informations entreprise enregistrées. Elles seront "
                                "utilisées sur les prochaines factures PDF.")

    def edit_smtp(self):
        show_smtp_dialog(self.winfo_toplevel())

    def edit_mail_template(self):
        show_mail_template_dialog(self.winfo_toplevel())

    def edit_db_config(self):
        if show_db_config_dialog(self.winfo_toplevel()):
            messagebox.showinfo(
                "Paramètres",
                "Connexion enregistrée. Elle sera utilisée dès la prochaine requête.",
            )

    def check_updates(self):
        """Ouvre un dialogue si une nouvelle version GitHub est disponible et propose l'installation."""
        try:
            check_and_maybe_update(ask_user=True)
        except Exception as e:
            messagebox.showerror("Mise à jour", f"Impossible de vérifier les mises à jour.\n\n{e}")

    def show_changelog(self):
        """Fenêtre défilante avec le journal des versions (CHANGELOG.md)."""
        win = tk.Toplevel(self)
        win.title(f"Notes de version — {__app_name__} v{__version__}")
        win.geometry("640x520")
        win.transient(self.winfo_toplevel())

        frame = ttk.Frame(win, padding=8)
        frame.pack(fill="both", expand=True)

        text = tk.Text(frame, wrap="word", font=("TkDefaultFont", 10), padx=8, pady=8)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        text.insert("1.0", load_changelog())
        text.configure(state="disabled")

        ttk.Button(win, text="Fermer", command=win.destroy).pack(pady=(0, 8))

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
