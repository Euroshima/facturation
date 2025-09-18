# === Paramètres de l'app ===
MY_INFO = {
    "nom_entreprise": "Boisset Didier",
    "nom": "Boisset Didier",
    "adresse": "3B route d'orleans\n89113 Fleury-la-vallée",
    "siret": "41337828200029",
    "email": "dimanche.boisset@gmail.com",
    "telephone": "06 12 77 26 17",
}

# Dossier et base
DB_FILE    = "data/invoices.db"
PDF_FOLDER = "data/factures_pdf"

# Devise à afficher (ex: "€", "CHF", "£", "$")
CURRENCY = "€"

# ---- Options visuelles pour l'en-tête façon INTIA ----
# Affiché sous le cartouche FACTURE, à droite
HEADER_VERSION = "1.0"         # texte libre (ex: "1.0")
HEADER_CLIENT_REFERENCE = ""   # ex: "C-000001" ; laisse vide si tu ne veux rien
