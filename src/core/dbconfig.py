# src/core/dbconfig.py — configuration de connexion à la base
"""
Les identifiants de la base ne sont pas dans le code (dépôt public).

Résolution, par priorité décroissante :
  1. variables d'environnement DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
  2. fichier de config utilisateur écrit par l'application :
       Windows : %APPDATA%\\Facturation\\db_config.ini
       autres  : ~/.config/facturation/db_config.ini
  3. fichier db_config.ini à côté de l'exe / à la racine du projet (compat)

`port` et `name` ont une valeur par défaut ; `host`, `user`, `password` sont
obligatoires.
"""

import configparser
import os
import sys

_KEYS = ("host", "port", "name", "user", "password")
_ENV = {
    "host": "DB_HOST", "port": "DB_PORT", "name": "DB_NAME",
    "user": "DB_USER", "password": "DB_PASSWORD",
}
_DEFAULTS = {"port": "5432", "name": "facturation"}
_REQUIRED = ("host", "user", "password")
CONFIG_FILENAME = "db_config.ini"
_APP_DIR = "Facturation"


def config_file_path() -> str:
    """Emplacement (créé si besoin) du fichier de config utilisateur."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, _APP_DIR)
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        folder = os.path.join(base, "facturation")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        pass
    return os.path.join(folder, CONFIG_FILENAME)


def _legacy_paths():
    if getattr(sys, "frozen", False):
        yield os.path.join(os.path.dirname(sys.executable), CONFIG_FILENAME)
    yield os.path.join(os.getcwd(), CONFIG_FILENAME)
    here = os.path.dirname(os.path.abspath(__file__))
    yield os.path.normpath(os.path.join(here, "..", "..", CONFIG_FILENAME))


def _read_ini(path: str) -> dict:
    out = {}
    try:
        if os.path.isfile(path):
            cp = configparser.ConfigParser()
            cp.read(path, encoding="utf-8")
            if cp.has_section("database"):
                for k in _KEYS:
                    if cp.has_option("database", k):
                        v = cp.get("database", k).strip()
                        if v:
                            out[k] = v
    except Exception:
        pass
    return out


def read_saved_config() -> dict:
    """Valeurs actuellement enregistrées (fichier utilisateur puis legacy),
    complétées par les défauts. Sert à pré-remplir la fenêtre de paramètres."""
    values = dict(_DEFAULTS)
    for path in _legacy_paths():
        values.update(_read_ini(path))
    values.update(_read_ini(config_file_path()))
    return values


def load_db_config() -> dict:
    """Config complète et valide, sinon lève RuntimeError."""
    values = read_saved_config()
    for k, env in _ENV.items():
        v = os.environ.get(env)
        if v and v.strip():
            values[k] = v.strip()

    missing = [k for k in _REQUIRED if not values.get(k)]
    if missing:
        raise RuntimeError(
            "Configuration de la base de données incomplète : "
            + ", ".join(missing) + "."
        )
    return {k: values.get(k, "") for k in _KEYS}


def save_db_config(values: dict) -> str:
    """Écrit la config dans le fichier utilisateur. Retourne son chemin."""
    path = config_file_path()
    cp = configparser.ConfigParser()
    cp["database"] = {
        k: str(values.get(k, _DEFAULTS.get(k, ""))).strip() for k in _KEYS
    }
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)
    return path


def build_url(values: dict) -> str:
    v = {**_DEFAULTS, **{k: (values.get(k) or "").strip() for k in _KEYS if values.get(k)}}
    return f"postgresql://{v.get('user','')}:{v.get('password','')}@{v.get('host','')}:{v.get('port','5432')}/{v.get('name','facturation')}"


def database_url() -> str:
    return build_url(load_db_config())
