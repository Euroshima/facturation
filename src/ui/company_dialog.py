# src/ui/company_dialog.py — fenêtre « Mon entreprise » (identité sur les factures)
import tkinter as tk
from tkinter import ttk, messagebox

from core import settings
from core.appconfig import load_section, save_section


class CompanyDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.saved = False
        self.title("Mon entreprise")
        self.resizable(False, False)

        saved = load_section("entreprise")
        current = dict(settings._DEFAULT_MY_INFO)
        current.update({k: v for k, v in saved.items() if v})

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(
            frm,
            text="Ces informations apparaissent sur chaque facture PDF.",
            wraplength=460,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._widgets = {}
        for i, (key, label, kind) in enumerate(settings.COMPANY_FIELDS, start=1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="ne", padx=(0, 8), pady=3)
            val = str(current.get(key, "") or "")
            if kind == "text":
                w = tk.Text(frm, width=46, height=3, wrap="word",
                            font=("TkDefaultFont", 9))
                w.insert("1.0", val)
            else:
                w = ttk.Entry(frm, width=48)
                w.insert(0, val)
            w.grid(row=i, column=1, sticky="we", pady=3)
            self._widgets[key] = (w, kind)

        btns = ttk.Frame(frm)
        btns.grid(row=len(settings.COMPANY_FIELDS) + 1, column=0, columnspan=2,
                  sticky="we", pady=(12, 0))
        ttk.Button(btns, text="Annuler", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Enregistrer", command=self._save).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())

        try:
            self.update_idletasks()
        except Exception:
            pass
        self._center()
        self.deiconify()
        self.lift()
        try:
            self.attributes("-topmost", True)
            self.after(500, lambda: self.attributes("-topmost", False))
        except Exception:
            pass
        try:
            self.focus_force()
        except Exception:
            pass
        self.after(50, self._try_grab)

    def _try_grab(self, tries=0):
        try:
            self.grab_set()
        except Exception:
            if tries < 10:
                self.after(100, lambda: self._try_grab(tries + 1))

    def _center(self):
        try:
            w = self.winfo_reqwidth() or 560
            h = self.winfo_reqheight() or 480
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 4)}")
        except Exception:
            pass

    def _values(self):
        out = {}
        for key, (w, kind) in self._widgets.items():
            if kind == "text":
                out[key] = w.get("1.0", "end").strip()
            else:
                out[key] = w.get().strip()
        return out

    def _save(self):
        vals = self._values()
        delai = vals.get("delai_paiement_jours", "").strip()
        if delai and not delai.isdigit():
            messagebox.showwarning("Champ invalide",
                                   "Le délai de paiement doit être un nombre de jours.",
                                   parent=self)
            return
        try:
            save_section("entreprise", vals)
            settings.reload_my_info()
        except Exception as e:
            messagebox.showerror("Enregistrement", f"Impossible d'enregistrer :\n{e}", parent=self)
            return
        self.saved = True
        self.destroy()

    def _cancel(self):
        self.saved = False
        self.destroy()


def show_company_dialog(parent) -> bool:
    dlg = CompanyDialog(parent)
    dlg.wait_window()
    return dlg.saved
