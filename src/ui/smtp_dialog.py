# src/ui/smtp_dialog.py — fenêtre « E-mail (SMTP) »
import tkinter as tk
from tkinter import ttk, messagebox

from core.mailer import SMTP_FIELDS, load_smtp, save_smtp, send_via_smtp
from .dialog_util import make_visible


class SmtpDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.saved = False
        self.title("E-mail (SMTP)")
        self.resizable(False, False)

        current = load_smtp()

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(
            frm,
            text="Serveur d'envoi pour expédier les factures par e-mail.\n"
                 "Exemple Gmail : smtp.gmail.com, port 587, sécurité starttls, "
                 "mot de passe = « mot de passe d'application ».",
            wraplength=420, justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._entries = {}
        for i, (key, label, kind) in enumerate(SMTP_FIELDS, start=1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=3)
            e = ttk.Entry(frm, width=34, show="•" if kind == "secret" else "")
            e.insert(0, str(current.get(key, "") or ""))
            e.grid(row=i, column=1, sticky="we", pady=3)
            self._entries[key] = e

        btns = ttk.Frame(frm)
        btns.grid(row=len(SMTP_FIELDS) + 1, column=0, columnspan=2, sticky="we", pady=(12, 0))
        ttk.Button(btns, text="Envoyer un test", command=self._test).pack(side="left")
        ttk.Button(btns, text="Annuler", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Enregistrer", command=self._save).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        make_visible(self)

    def _values(self):
        return {k: e.get().strip() for k, e in self._entries.items()}

    def _test(self):
        vals = self._values()
        save_smtp(vals)
        to = vals.get("from_addr") or vals.get("user")
        if not to:
            messagebox.showwarning("Test", "Renseigne l'adresse expéditeur d'abord.", parent=self)
            return
        ok, err = send_via_smtp(to, "Test — Hytris Facturation",
                                "Ceci est un e-mail de test.", None)
        if ok:
            messagebox.showinfo("Test", f"E-mail de test envoyé à {to}.", parent=self)
        else:
            messagebox.showerror("Test", f"Échec :\n{err}", parent=self)

    def _save(self):
        try:
            save_smtp(self._values())
        except Exception as e:
            messagebox.showerror("Enregistrement", str(e), parent=self)
            return
        self.saved = True
        self.destroy()

    def _cancel(self):
        self.saved = False
        self.destroy()


def show_smtp_dialog(parent) -> bool:
    dlg = SmtpDialog(parent)
    dlg.wait_window()
    return dlg.saved
