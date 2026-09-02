# core/paths.py — construction des chemins de PDF, un sous-dossier par client
import os
import re

from core.settings import PDF_FOLDER

# Caractères interdits dans un nom de dossier (Windows + POSIX) + caractères de contrôle
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Noms réservés sous Windows (interdits même avec une extension)
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def client_folder_name(client) -> str:
    """Nom de dossier lisible et sûr pour un client.

    Priorité : nom_entreprise, sinon "prénom nom", sinon "client_<id>".
    """
    def _get(key):
        try:
            val = client.get(key)
        except AttributeError:
            val = client[key] if key in client else None
        return ("" if val is None else str(val)).strip()

    name = _get("nom_entreprise")
    if not name:
        name = f"{_get('prenom')} {_get('nom')}".strip()
    if not name:
        cid = _get("id") or "inconnu"
        name = f"client_{cid}"

    # Nettoyage : caractères interdits -> "_", espaces multiples -> un seul,
    # pas de point ni d'espace en fin (Windows).
    name = _INVALID_CHARS.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(". ")
    if name.lower() in _RESERVED:
        name = f"{name}_"
    return name or "client_inconnu"


def client_pdf_dir(client) -> str:
    """Dossier des PDF d'un client (créé si absent)."""
    path = os.path.join(PDF_FOLDER, client_folder_name(client))
    os.makedirs(path, exist_ok=True)
    return path


def invoice_pdf_path(client, facture_num) -> str:
    """Chemin complet du PDF d'une facture, rangé dans le dossier du client."""
    return os.path.join(client_pdf_dir(client), f"facture_{facture_num}.pdf")
