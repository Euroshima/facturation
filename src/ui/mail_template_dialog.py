# src/ui/mail_template_dialog.py — édition des modèles d'e-mail
import tkinter as tk
from tkinter import ttk

from core.mailtemplate import KINDS, PLACEHOLDERS, load_template, save_template, render
from .dialog_util import make_visible

_PREVIEW_CTX = {
    "facture": "20260903-0007",
    "societe": "Boisset Didier",
    "client": "ACME SARL",
    "total": "120,00 €",
    "date": "03/09/2026",
    "echeance": "03/10/2026",
    "retard": "12",
}


class _TemplateEditor(ttk.Frame):
    """Sujet + corps + aperçu pour un modèle donné."""

    def __init__(self, master, kind):
        super().__init__(master, padding=10)
        self.kind = kind
        _, self.def_subject, self.def_body, _ = KINDS[kind]
        subject, body = load_template(kind)

        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Sujet").grid(row=0, column=0, sticky="w")
        self.e_subject = ttk.Entry(self)
        self.e_subject.insert(0, subject)
        self.e_subject.grid(row=1, column=0, sticky="we", pady=(0, 8))

        ttk.Label(self, text="Corps du message").grid(row=2, column=0, sticky="w")
        self.t_body = tk.Text(self, width=64, height=12, wrap="word",
                              font=("TkDefaultFont", 10))
        self.t_body.insert("1.0", body)
        self.t_body.grid(row=3, column=0, sticky="nsew")
        self.rowconfigure(3, weight=1)

        self.lbl_preview = ttk.Label(self, text="", foreground="#337",
                                     wraplength=520, justify="left")
        self.lbl_preview.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.e_subject.bind("<KeyRelease>", lambda e: self.refresh_preview())
        self.t_body.bind("<KeyRelease>", lambda e: self.refresh_preview())

        ttk.Button(self, text="Réinitialiser ce modèle", command=self.reset).grid(
            row=5, column=0, sticky="w", pady=(8, 0))
        self.refresh_preview()

    def refresh_preview(self):
        self.lbl_preview.config(
            text="Aperçu — Sujet : " + render(self.e_subject.get(), _PREVIEW_CTX))

    def reset(self):
        self.e_subject.delete(0, "end")
        self.e_subject.insert(0, self.def_subject)
        self.t_body.delete("1.0", "end")
        self.t_body.insert("1.0", self.def_body)
        self.refresh_preview()

    def save(self):
        save_template(self.e_subject.get(),
                      self.t_body.get("1.0", "end").rstrip("\n"),
                      kind=self.kind)


class MailTemplateDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.saved = False
        self.title("Modèles d'e-mail")
        self.resizable(True, True)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(2, weight=1)

        ph = ", ".join("{" + k + "}" for k in PLACEHOLDERS)
        ttk.Label(frm, text="Ces modèles servent de point de départ à chaque envoi "
                            "(modifiables au cas par cas).").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Champs disponibles : " + ph, foreground="#555",
                  wraplength=520).grid(row=1, column=0, sticky="w", pady=(2, 10))

        nb = ttk.Notebook(frm)
        nb.grid(row=2, column=0, sticky="nsew")
        self.editors = {}
        for kind, (_, _, _, label) in KINDS.items():
            ed = _TemplateEditor(nb, kind)
            nb.add(ed, text=label)
            self.editors[kind] = ed

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, sticky="we", pady=(12, 0))
        ttk.Button(btns, text="Annuler", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Enregistrer", command=self._save).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        make_visible(self)

    def _save(self):
        for ed in self.editors.values():
            ed.save()
        self.saved = True
        self.destroy()

    def _cancel(self):
        self.saved = False
        self.destroy()


def show_mail_template_dialog(parent) -> bool:
    dlg = MailTemplateDialog(parent)
    dlg.wait_window()
    return dlg.saved
