# src/core/mailer.py — envoi de la facture PDF par e-mail
"""
Deux modes :
  - SMTP direct (configuré dans Paramètres → E-mail) : la pièce jointe part
    vraiment depuis l'application.
  - Repli « mailto: » : ouvre le logiciel de messagerie du poste avec le
    destinataire / sujet / corps pré-remplis ; la pièce jointe doit être
    ajoutée à la main (mailto ne permet pas les pièces jointes).
"""

import os
import smtplib
import ssl
import urllib.parse
import webbrowser
from email.message import EmailMessage

from core.appconfig import load_section, save_section

SMTP_FIELDS = [
    ("host", "Serveur SMTP", "entry"),
    ("port", "Port", "entry"),
    ("user", "Identifiant", "entry"),
    ("password", "Mot de passe", "secret"),
    ("from_addr", "Adresse expéditeur", "entry"),
    ("security", "Sécurité (starttls / ssl / aucune)", "entry"),
]


def load_smtp() -> dict:
    cfg = {"port": "587", "security": "starttls"}
    cfg.update({k: v for k, v in load_section("smtp").items() if v})
    return cfg


def save_smtp(values: dict) -> str:
    return save_section("smtp", values)


def smtp_is_configured() -> bool:
    c = load_smtp()
    return bool(c.get("host") and c.get("from_addr"))


def send_via_smtp(to_addr, subject, body, attachment_path=None):
    """Envoie l'e-mail. Retourne (True, '') ou (False, message)."""
    c = load_smtp()
    host = (c.get("host") or "").strip()
    if not host:
        return False, "Serveur SMTP non configuré (Paramètres → E-mail)."
    try:
        port = int(c.get("port") or 587)
    except ValueError:
        port = 587
    user = (c.get("user") or "").strip()
    pwd = c.get("password") or ""
    from_addr = (c.get("from_addr") or user).strip()
    security = (c.get("security") or "starttls").strip().lower()

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body or "")

    if attachment_path and os.path.isfile(attachment_path):
        try:
            with open(attachment_path, "rb") as f:
                data = f.read()
            msg.add_attachment(data, maintype="application", subtype="pdf",
                               filename=os.path.basename(attachment_path))
        except Exception as e:
            return False, f"Pièce jointe illisible : {e}"

    try:
        if security == "ssl":
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
                if user:
                    s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo()
                if security == "starttls":
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                if user:
                    s.login(user, pwd)
                s.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


def open_mailto(to_addr, subject, body):
    """Ouvre le client mail par défaut (sans pièce jointe)."""
    q = urllib.parse.urlencode({"subject": subject or "", "body": body or ""},
                               quote_via=urllib.parse.quote)
    webbrowser.open(f"mailto:{to_addr or ''}?{q}")
