# src/ui/send_email_dialog.py — composer et envoyer la facture par e-mail
import os
import tkinter as tk
from tkinter import ttk, messagebox

from core.mailer import smtp_is_configured, send_via_smtp, open_mailto
from core.settings import MY_INFO
from .dialog_util import make_visible


class SendEmailDialog(tk.Toplevel):
    def __init__(self, parent, *, facture_num, to_addr, pdf_path):
        super().__init__(parent)
        self.sent = False
        self._pdf = pdf_path
        self.title(f"Envoyer la facture {facture_num}")
        self.resizable(False, False)

        societe = MY_INFO.get("nom_entreprise") or MY_INFO.get("nom") or ""
        default_subject = f"Facture {facture_num}" + (f" — {societe}" if societe else "")
        default_body = (
            "Bonjour,\n\n"
            f"Veuillez trouver ci-joint la facture {facture_num}.\n\n"
            "Cordialement,\n"
            f"{societe}"
        )

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Destinataire").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=3)
        self.e_to = ttk.Entry(frm, width=48)
        self.e_to.insert(0, to_addr or "")
        self.e_to.grid(row=0, column=1, sticky="we", pady=3)

        ttk.Label(frm, text="Sujet").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        self.e_subject = ttk.Entry(frm, width=48)
        self.e_subject.insert(0, default_subject)
        self.e_subject.grid(row=1, column=1, sticky="we", pady=3)

        ttk.Label(frm, text="Message").grid(row=2, column=0, sticky="ne", padx=(0, 8), pady=3)
        self.t_body = tk.Text(frm, width=48, height=8, wrap="word", font=("TkDefaultFont", 9))
        self.t_body.insert("1.0", default_body)
        self.t_body.grid(row=2, column=1, sticky="we", pady=3)

        pj = os.path.basename(pdf_path) if pdf_path and os.path.isfile(pdf_path) else "(PDF introuvable)"
        ttk.Label(frm, text=f"Pièce jointe : {pj}", foreground="#555").grid(
            row=3, column=1, sticky="w", pady=(2, 8))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="we")
        ttk.Button(btns, text="Ouvrir dans ma messagerie", command=self._mailto).pack(side="left")
        ttk.Button(btns, text="Fermer", command=self.destroy).pack(side="right")
        self.btn_send = ttk.Button(btns, text="Envoyer (SMTP)", command=self._send)
        self.btn_send.pack(side="right", padx=6)
        if not smtp_is_configured():
            self.btn_send.state(["disabled"])
            ttk.Label(frm, text="SMTP non configuré (Paramètres → E-mail) — "
                                "utilisez « Ouvrir dans ma messagerie ».",
                      foreground="#a00", wraplength=440).grid(
                row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.bind("<Escape>", lambda e: self.destroy())
        make_visible(self)

    def _fields(self):
        return (self.e_to.get().strip(),
                self.e_subject.get().strip(),
                self.t_body.get("1.0", "end").strip())

    def _send(self):
        to, subject, body = self._fields()
        if not to:
            messagebox.showwarning("Envoi", "Renseignez le destinataire.", parent=self)
            return
        self.btn_send.state(["disabled"])
        self.update_idletasks()
        ok, err = send_via_smtp(to, subject, body, self._pdf)
        self.btn_send.state(["!disabled"])
        if ok:
            self.sent = True
            messagebox.showinfo("Envoi", f"Facture envoyée à {to}.", parent=self)
            self.destroy()
        else:
            messagebox.showerror("Envoi", f"Échec de l'envoi :\n{err}", parent=self)

    def _mailto(self):
        to, subject, body = self._fields()
        note = "\n\n(Pensez à joindre le PDF : " + (self._pdf or "") + ")"
        open_mailto(to, subject, body + note)


def show_send_email_dialog(parent, *, facture_num, to_addr, pdf_path) -> bool:
    dlg = SendEmailDialog(parent, facture_num=facture_num, to_addr=to_addr, pdf_path=pdf_path)
    dlg.wait_window()
    return dlg.sent
