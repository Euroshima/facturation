# src/core/appconfig.py — petit stockage de configuration par utilisateur
"""
Fichier unique %APPDATA%\\Facturation\\facturation.ini (Windows) ou
~/.config/facturation/facturation.ini, avec des sections nommées
([entreprise], [smtp], …). Lecture/écriture simples, tout en texte.

(La connexion BDD garde son fichier séparé, voir core/dbconfig.py.)
"""

import configparser
import os
import sys

APP_DIR_NAME = "Facturation"
FILE_NAME = "facturation.ini"


def config_dir() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, APP_DIR_NAME)
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        folder = os.path.join(base, "facturation")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        pass
    return folder


def config_path() -> str:
    return os.path.join(config_dir(), FILE_NAME)


def _read() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    try:
        cp.read(config_path(), encoding="utf-8")
    except Exception:
        pass
    return cp


def load_section(name: str) -> dict:
    cp = _read()
    if cp.has_section(name):
        return {k: v for k, v in cp.items(name)}
    return {}


def save_section(name: str, values: dict) -> str:
    """Remplace la section `name` par `values`. Retourne le chemin du fichier."""
    cp = _read()
    if not cp.has_section(name):
        cp.add_section(name)
    else:
        for k in list(cp[name].keys()):
            cp.remove_option(name, k)
    for k, v in values.items():
        cp.set(name, str(k), "" if v is None else str(v))
    path = config_path()
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)
    return path
