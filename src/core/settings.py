# === Paramètres de l'app ===

# Valeurs par défaut de l'identité entreprise (imprimées sur chaque facture).
# Elles sont surchargées par ce que l'utilisateur saisit dans
# Paramètres → Mon entreprise (stocké dans %APPDATA%\Facturation\facturation.ini).
_DEFAULT_MY_INFO = {
    "nom_entreprise": "Boisset Didier",
    "nom": "Boisset Didier",
    "adresse": "3B route d'orleans\n89113 Fleury-la-vallée",
    "siret": "41337828200029",
    "email": "dimanche.boisset@gmail.com",
    "telephone": "06 12 77 26 17",
    # Optionnels : iban, bic, tva_intracom, delai_paiement_jours,
    # mentions_legales, pied_de_page, reference_client
}

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

# Dossier et base
DB_FILE = "data/invoices.db"
PDF_FOLDER = "data/factures_pdf"

# Devise à afficher (ex: "€", "CHF", "£", "$")
CURRENCY = "€"
