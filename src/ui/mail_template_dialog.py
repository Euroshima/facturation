# src/ui/mail_template_dialog.py — édition du modèle d'e-mail
import tkinter as tk
from tkinter import ttk

from core.mailtemplate import (
    DEFAULT_SUBJECT, DEFAULT_BODY, PLACEHOLDERS, load_template, save_template, render,
)
from .dialog_util import make_visible

_PREVIEW_CTX = {
    "facture": "20260903-0007",
    "societe": "Boisset Didier",
    "client": "ACME SARL",
    "total": "120,00 €",
    "date": "03/09/2026",
    "echeance": "03/10/2026",
}


class MailTemplateDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.saved = False
        self.title("Modèle d'e-mail")
        self.resizable(True, True)

        subject, body = load_template()

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)

        ph = ", ".join("{" + k + "}" for k in PLACEHOLDERS)
        ttk.Label(frm, text="Ce modèle sert de point de départ à chaque envoi "
                             "(modifiable au cas par cas).").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Champs disponibles : " + ph, foreground="#555",
                  wraplength=520).grid(row=1, column=0, sticky="w", pady=(2, 10))

        ttk.Label(frm, text="Sujet").grid(row=2, column=0, sticky="w")
        self.e_subject = ttk.Entry(frm)
        self.e_subject.insert(0, subject)
        self.e_subject.grid(row=3, column=0, sticky="we", pady=(0, 8))

        ttk.Label(frm, text="Corps du message").grid(row=4, column=0, sticky="w")
        self.t_body = tk.Text(frm, width=64, height=12, wrap="word",
                              font=("TkDefaultFont", 10))
        self.t_body.insert("1.0", body)
        self.t_body.grid(row=5, column=0, sticky="nsew")
        frm.rowconfigure(5, weight=1)

        self.lbl_preview = ttk.Label(frm, text="", foreground="#337",
                                     wraplength=520, justify="left")
        self.lbl_preview.grid(row=6, column=0, sticky="w", pady=(8, 0))
        self.e_subject.bind("<KeyRelease>", lambda e: self._refresh_preview())
        self.t_body.bind("<KeyRelease>", lambda e: self._refresh_preview())

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, sticky="we", pady=(12, 0))
        ttk.Button(btns, text="Réinitialiser", command=self._reset).pack(side="left")
        ttk.Button(btns, text="Annuler", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Enregistrer", command=self._save).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        self._refresh_preview()
        make_visible(self)

    def _refresh_preview(self):
        subj = render(self.e_subject.get(), _PREVIEW_CTX)
        self.lbl_preview.config(text="Aperçu — Sujet : " + subj)

    def _reset(self):
        self.e_subject.delete(0, "end")
        self.e_subject.insert(0, DEFAULT_SUBJECT)
        self.t_body.delete("1.0", "end")
        self.t_body.insert("1.0", DEFAULT_BODY)
        self._refresh_preview()

    def _save(self):
        save_template(self.e_subject.get(), self.t_body.get("1.0", "end").rstrip("\n"))
        self.saved = True
        self.destroy()

    def _cancel(self):
        self.saved = False
        self.destroy()


def show_mail_template_dialog(parent) -> bool:
    dlg = MailTemplateDialog(parent)
    dlg.wait_window()
    return dlg.saved
