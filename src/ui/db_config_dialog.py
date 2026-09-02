# src/ui/db_config_dialog.py — fenêtre de configuration de la connexion BDD
import tkinter as tk
from tkinter import ttk, messagebox

from core.dbconfig import read_saved_config, save_db_config, build_url
from core.db import try_connect

_FIELDS = [
    ("host", "Hôte / IP", False),
    ("port", "Port", False),
    ("name", "Base", False),
    ("user", "Utilisateur", False),
    ("password", "Mot de passe", True),
]


class DbConfigDialog(tk.Toplevel):
    """Modale : saisie/édition des identifiants de connexion PostgreSQL."""

    def __init__(self, parent, *, first_run=False):
        super().__init__(parent)
        self.saved = False
        self.title("Connexion à la base de données")
        self.resizable(False, False)
        self.transient(parent)

        current = read_saved_config()
        self._vars = {}

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        if first_run:
            ttk.Label(
                frm,
                text="Renseignez la connexion à la base PostgreSQL pour démarrer.",
                wraplength=360,
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        for i, (key, label, secret) in enumerate(_FIELDS, start=1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=3)
            var = tk.StringVar(value=current.get(key, ""))
            ent = ttk.Entry(frm, textvariable=var, width=32, show="•" if secret else "")
            ent.grid(row=i, column=1, sticky="we", pady=3)
            self._vars[key] = var

        btns = ttk.Frame(frm)
        btns.grid(row=len(_FIELDS) + 1, column=0, columnspan=2, sticky="we", pady=(12, 0))
        ttk.Button(btns, text="Tester la connexion", command=self._test).pack(side="left")
        ttk.Button(btns, text="Annuler", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Enregistrer", command=self._save).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self._cancel())

        self.grab_set()
        self.update_idletasks()
        self._center_on(parent)

    # ---- helpers ----
    def _values(self):
        return {k: v.get().strip() for k, v in self._vars.items()}

    def _missing(self, vals):
        return [lbl for key, lbl, _ in _FIELDS
                if key in ("host", "user", "password") and not vals.get(key)]

    def _center_on(self, parent):
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 3}")
        except Exception:
            pass

    # ---- actions ----
    def _test(self):
        vals = self._values()
        miss = self._missing(vals)
        if miss:
            messagebox.showwarning("Champs requis", "Manquant : " + ", ".join(miss), parent=self)
            return
        ok, err = try_connect(build_url(vals))
        if ok:
            messagebox.showinfo("Connexion", "Connexion réussie.", parent=self)
        else:
            messagebox.showerror("Connexion", f"Échec :\n{err}", parent=self)

    def _save(self):
        vals = self._values()
        miss = self._missing(vals)
        if miss:
            messagebox.showwarning("Champs requis", "Manquant : " + ", ".join(miss), parent=self)
            return
        ok, err = try_connect(build_url(vals))
        if not ok and not messagebox.askyesno(
            "Connexion",
            f"La connexion a échoué :\n{err}\n\nEnregistrer quand même ?",
            parent=self,
        ):
            return
        try:
            save_db_config(vals)
        except Exception as e:
            messagebox.showerror("Enregistrement", f"Impossible d'écrire la config :\n{e}", parent=self)
            return
        self.saved = True
        self.destroy()

    def _cancel(self):
        self.saved = False
        self.destroy()


def show_db_config_dialog(parent, first_run=False) -> bool:
    """Ouvre la modale. Retourne True si la config a été enregistrée."""
    dlg = DbConfigDialog(parent, first_run=first_run)
    parent.wait_window(dlg)
    return dlg.saved
