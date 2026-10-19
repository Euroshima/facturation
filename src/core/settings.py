# === Paramètres de l'app ===

# Identité de l'entreprise (imprimée sur chaque facture) : aucune valeur par
# défaut dans le code, tout vient de Paramètres → Mon entreprise (stocké dans
# %APPDATA%\Facturation\facturation.ini). Une facture n'est créée que si
# nom, adresse, SIRET et IBAN sont renseignés (voir pdf.pdfgen).
# Optionnels : bic, tva_intracom, email, telephone, delai_paiement_jours,
# mentions_legales, pied_de_page, reference_client
_DEFAULT_MY_INFO = {}

# Clés de l'identité entreprise (ordre d'affichage dans la fenêtre)
COMPANY_FIELDS = [
    ("nom_entreprise", "Nom / Raison sociale", "entry"),
    ("nom", "Nom du contact", "entry"),
    ("adresse", "Adresse", "text"),
    ("siret", "SIRET", "entry"),
    ("tva_intracom", "N° TVA intracom.", "entry"),
    ("email", "Email", "entry"),
    ("telephone", "Téléphone", "entry"),
    ("iban", "IBAN", "entry"),
    ("bic", "BIC", "entry"),
    ("delai_paiement_jours", "Délai de paiement (jours)", "entry"),
    ("mentions_legales", "Mentions légales (vide = texte par défaut)", "text"),
    ("pied_de_page", "Ligne de pied de page (optionnel)", "entry"),
]

MY_INFO = dict(_DEFAULT_MY_INFO)


def reload_my_info():
    """Recharge MY_INFO (défauts + valeurs enregistrées) sur place."""
    MY_INFO.clear()
    MY_INFO.update(_DEFAULT_MY_INFO)
    try:
        from core.appconfig import load_section
        for k, v in load_section("entreprise").items():
            if v is not None and str(v).strip() != "":
                MY_INFO[k] = v
    except Exception:
        pass
    return MY_INFO


reload_my_info()

import os
import sys


def _base_dir():
    """Dossier de l'exe (version installée) ou racine du projet : les PDF ne
    dépendent pas du dossier depuis lequel l'application est lancée."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


# Dossier des PDF
PDF_FOLDER = os.path.join(_base_dir(), "data", "factures_pdf")

# Devise à afficher (ex: "€", "CHF", "£", "$")
CURRENCY = "€"
