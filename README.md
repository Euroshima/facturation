
# Facturier (Tkinter + SQLite + ReportLab)

Une petite application de facturation **hors ligne** pour Windows (fonctionne aussi sur macOS/Linux).  
PDF propres, base **SQLite**, recherche, édition de factures, gestion des clients, et génération de PDF.

---

## 📦 Structure proposée

```
facturation/
├─ data/
│  ├─ invoices.db             # Base SQLite
│  └─ factures_pdf/           # Dossier des PDF
├─ src/
│  ├─ core/                   # Cœur métier / persistance
│  │  ├─ __init__.py
│  │  ├─ db.py
│  │  └─ settings.py
│  ├─ pdf/                    # Génération des PDFs
│  │  ├─ __init__.py
│  │  └─ pdfgen.py
│  ├─ ui/                     # Interface Tkinter
│  │  ├─ __init__.py
│  │  ├─ app.py
│  │  ├─ widgets.py
│  │  ├─ tab_create.py
│  │  ├─ tab_search.py
│  │  └─ tab_clients.py
│  └─ main.py                 # Point d’entrée
└─ README.md
```

> Si vous avez déjà ces fichiers à la racine, vous pouvez utiliser le script **`reorganize.ps1`** fourni pour ranger automatiquement (Windows PowerShell).

---

## 🔧 Installation rapide

1) **Python 3.11+** recommandé (3.12/3.13 OK).  
2) Créez un environnement virtuel et installez les dépendances :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install reportlab
```

*(Tkinter est inclus avec Python sur Windows ; aucun paquet à installer.)*

---

## 🚚 Réorganisation automatique (Windows)

1) Placez **tous vos fichiers actuels** dans un dossier, par ex. `D:\DEV\Facturation`.
2) Téléchargez `reorganize.ps1` (fourni avec ce README) dans ce dossier.
3) **Exécutez** dans PowerShell (autorisez l'exécution si besoin) :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.eorganize.ps1
```

Le script va :
- Créer `data/` et `src/` (avec sous-dossiers).
- Déplacer `invoices.db` et `factures_pdf/` dans `data/`.
- Déplacer vos fichiers `.py` aux bons endroits.
- Insérer automatiquement des `__init__.py` si absents.
- **Mettre à jour les imports** dans vos fichiers pour refléter la nouvelle structure.

---

## ▶️ Lancer l’application

Depuis la racine du projet (là où se trouve *README.md*) :

```powershell
.\.venv\Scripts\Activate.ps1
python .\src\main.py
```

> Si vous voulez un double-clic : créez un raccourci vers `python.exe` qui pointe sur `src\main.py`.

---

## 🧭 Imports après réorganisation

Vos imports deviennent :

```python
# avant
# from db import init_db, ...
# from pdfgen import create_pdf

# après
from core.db import init_db, money, save_client, update_client, find_or_create_client,     search_clients, search_invoices, generate_invoice_number,     insert_invoice, update_invoice, set_pdf_path, get_invoice_with_items

from pdf.pdfgen import create_pdf
from core.settings import MY_INFO, DB_FILE, PDF_FOLDER, CURRENCY
```

Et côté UI (si séparée en onglets) : rien à changer en dehors des imports vers `core.*` et `pdf.*`.

---

## ⚙️ Paramètres

Fichier : `src/core/settings.py`

```python
MY_INFO = {
    "nom_entreprise": "Boisset Didier",
    "nom": "Boisset Didier",
    "adresse": "3B route d'orleans\n89113 Fleury-la-vallée\nFrance",
    "siret": "41337828200029",
    "email": "dimanche.boisset@gmail.com",
    "telephone": "+33 6 00 00 00 00",
}

CURRENCY   = "€"
DB_FILE    = "data/invoices.db"
PDF_FOLDER = "data/factures_pdf"
```

> **Note** : Après réorganisation, **ne changez pas** `DB_FILE`/`PDF_FOLDER` si vous gardez la structure recommandée.

---

## 🧪 Création d’un exécutable (optionnel)

```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name Facturation .\src\main.py
```
Le binaire sera dans `dist/Facturation.exe`.

---

## ❓Dépannage rapide

- **Erreur `sqlite3.IntegrityError: UNIQUE constraint ...`**  
  Votre table clients a un index d’unicité ; vous essayez de créer un doublon.  
  → Utilisez le bouton *“Enregistrer/MAJ client”* (qui met à jour s’il existe), ou supprimez les doublons.

- **Polices ReportLab / accents**  
  Placez `DejaVuSans.ttf` à la racine si vous voulez garantir les accents ; sinon le fallback `Helvetica` est utilisé.

- **PDF qui se chevauchent**  
  Vous utilisez déjà un calcul de hauteur par ligne et un saut de page. Assurez-vous d’appeler la redessine de l’en‑tête après chaque `showPage()` si vous ajoutez des sauts supplémentaires.

---

## ✅ À faire ensuite (suggestions)
- Échéance + statut de paiement
- TVA par ligne & récap multi-taux
- Devis → Facture
- Envoi par e-mail + QR-code de virement
- Export CSV/Excel

Bon usage ! ✨
