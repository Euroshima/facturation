# src/core/mailtemplate.py — modèle d'e-mail réutilisable (sujet + corps)
"""
Un seul modèle global, enregistré dans facturation.ini [email_template].
Placeholders disponibles dans le sujet et le corps : voir PLACEHOLDERS.
La substitution est tolérante : un placeholder inconnu est laissé tel quel,
il ne fait jamais planter l'envoi.
"""

from core.appconfig import load_section, save_section

SECTION = "email_template"

DEFAULT_SUBJECT = "Facture {facture} — {societe}"
DEFAULT_BODY = (
    "Bonjour,\n\n"
    "Veuillez trouver ci-joint la facture {facture} d'un montant de {total}.\n\n"
    "Cordialement,\n"
    "{societe}"
)

# nom -> description (affichée dans la fenêtre d'édition)
PLACEHOLDERS = {
    "facture": "Numéro de facture",
    "societe": "Votre raison sociale",
    "client": "Nom du client",
    "total": "Montant TTC (ex. 120,00 €)",
    "date": "Date d'émission (JJ/MM/AAAA)",
    "echeance": "Date d'échéance (JJ/MM/AAAA)",
}


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def load_template():
    """Retourne (sujet, corps). Valeurs enregistrées, sinon défauts."""
    data = load_section(SECTION)
    subject = (data.get("subject") or "").strip() or DEFAULT_SUBJECT
    raw_body = data.get("body")
    body = raw_body.replace("\\n", "\n") if raw_body else DEFAULT_BODY
    return subject, body


def save_template(subject: str, body: str) -> str:
    subject = (subject or "").strip() or DEFAULT_SUBJECT
    body = body if (body or "").strip() else DEFAULT_BODY
    # Les retours à la ligne sont stockés en littéral \n pour éviter tout
    # souci de valeur multiligne dans le .ini.
    return save_section(SECTION, {
        "subject": subject.replace("\n", " ").strip(),
        "body": body.replace("\r\n", "\n").replace("\n", "\\n"),
    })


def render(template: str, context: dict) -> str:
    try:
        return (template or "").format_map(_SafeDict(context or {}))
    except Exception:
        return template or ""
