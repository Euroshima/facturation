# src/core/mailtemplate.py — modèle d'e-mail réutilisable (sujet + corps)
"""
Deux modèles globaux enregistrés dans facturation.ini : l'envoi normal
([email_template]) et la relance d'impayé ([email_template_relance]).
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

DEFAULT_RELANCE_SUBJECT = "Relance — facture {facture} échue depuis le {echeance}"
DEFAULT_RELANCE_BODY = (
    "Bonjour,\n\n"
    "Sauf erreur de notre part, la facture {facture} d'un montant de {total}, "
    "échue le {echeance}, reste impayée à ce jour ({retard} jours de retard).\n\n"
    "Nous vous remercions de bien vouloir procéder à son règlement. "
    "Si le paiement a été effectué entre-temps, merci de ne pas tenir compte "
    "de ce message.\n\n"
    "Cordialement,\n"
    "{societe}"
)

# clé de modèle -> (section ini, sujet par défaut, corps par défaut, libellé)
KINDS = {
    "facture": (SECTION, DEFAULT_SUBJECT, DEFAULT_BODY, "Envoi de facture"),
    "relance": ("email_template_relance", DEFAULT_RELANCE_SUBJECT,
                DEFAULT_RELANCE_BODY, "Relance d'impayé"),
}

# nom -> description (affichée dans la fenêtre d'édition)
PLACEHOLDERS = {
    "facture": "Numéro de facture",
    "societe": "Votre raison sociale",
    "client": "Nom du client",
    "total": "Montant TTC (ex. 120,00 €)",
    "date": "Date d'émission (JJ/MM/AAAA)",
    "echeance": "Date d'échéance (JJ/MM/AAAA)",
    "retard": "Jours de retard (0 si dans les temps)",
}


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def load_template(kind: str = "facture"):
    """Retourne (sujet, corps) du modèle demandé. Enregistrés, sinon défauts."""
    section, def_subject, def_body, _ = KINDS.get(kind, KINDS["facture"])
    data = load_section(section)
    subject = (data.get("subject") or "").strip() or def_subject
    raw_body = data.get("body")
    body = raw_body.replace("\\n", "\n") if raw_body else def_body
    return subject, body


def save_template(subject: str, body: str, kind: str = "facture") -> str:
    section, def_subject, def_body, _ = KINDS.get(kind, KINDS["facture"])
    subject = (subject or "").strip() or def_subject
    body = body if (body or "").strip() else def_body
    # Les retours à la ligne sont stockés en littéral \n pour éviter tout
    # souci de valeur multiligne dans le .ini.
    return save_section(section, {
        "subject": subject.replace("\n", " ").strip(),
        "body": body.replace("\r\n", "\n").replace("\n", "\\n"),
    })


def render(template: str, context: dict) -> str:
    try:
        return (template or "").format_map(_SafeDict(context or {}))
    except Exception:
        return template or ""
