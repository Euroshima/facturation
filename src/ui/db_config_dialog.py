# src/ui/db_config_dialog.py — fenêtre de configuration de la connexion BDD
import datetime
import os
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox

from core.dbconfig import read_saved_config, save_db_config, build_url
from core.db import try_connect


def _trace(msg):
    """Trace dans facturation-boot.log (même fichier que main.py)."""
    line = f"{datetime.datetime.now():%H:%M:%S.%f} | [dlg] {msg}\n"
    for base in (os.path.dirname(os.path.abspath(sys.executable)), tempfile.gettempdir()):
        try:
            with open(os.path.join(base, "facturation-boot.log"), "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
        except Exception:
            pass

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
        _trace("DbConfigDialog.__init__")
        super().__init__(parent)
        self.saved = False
        self.title("Connexion à la base de données")
        self.resizable(False, False)

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

        # --- Affichage robuste (aucun appel bloquant : pas de wait_visibility) ---
        _trace("dlg: widgets prêts")
        try:
            self.update_idletasks()
        except Exception:
            pass
        self._center_on_screen()
        self.deiconify()
        self.lift()
        try:
            self.attributes("-topmost", True)
            self.after(500, self._drop_topmost)
        except Exception:
            pass
        try:
            self.focus_force()
        except Exception:
            pass
        # grab_set en best-effort et différé : s'il échoue (fenêtre pas encore
        # mappée) on réessaie, mais on ne bloque jamais.
        self.after(50, self._try_grab)
        _trace("dlg: __init__ terminé")

    def _try_grab(self, tries=0):
        try:
            self.grab_set()
        except Exception:
            if tries < 10:
                self.after(100, lambda: self._try_grab(tries + 1))

    # ---- helpers ----
    def _drop_topmost(self):
        try:
            self.attributes("-topmost", False)
        except Exception:
            pass

    def _values(self):
        return {k: v.get().strip() for k, v in self._vars.items()}

    def _missing(self, vals):
        return [lbl for key, lbl, _ in _FIELDS
                if key in ("host", "user", "password") and not vals.get(key)]

    def _center_on_screen(self):
        try:
            w = self.winfo_reqwidth() or 380
            h = self.winfo_reqheight() or 260
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
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
    _trace("show_db_config_dialog: création")
    dlg = DbConfigDialog(parent, first_run=first_run)
    _trace("show_db_config_dialog: wait_window")
    dlg.wait_window()
    _trace(f"show_db_config_dialog: fermée (saved={dlg.saved})")
    return dlg.saved
