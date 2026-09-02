# src/core/dbconfig.py — configuration de connexion à la base (hors dépôt)
"""
Les identifiants de la base ne sont PAS dans le code (dépôt public).

Ordre de résolution :
  1. variables d'environnement DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
  2. fichier db_config.ini à côté de l'exe, ou à la racine du projet en dev
     [database]
     host = ...
     port = 5432
     name = facturation
     user = ...
     password = ...

`port` et `name` ont des valeurs par défaut ; `host`, `user`, `password` sont
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
CONFIG_FILENAME = "db_config.ini"


def _config_paths():
    if getattr(sys, "frozen", False):
        yield os.path.join(os.path.dirname(sys.executable), CONFIG_FILENAME)
    yield os.path.join(os.getcwd(), CONFIG_FILENAME)
    here = os.path.dirname(os.path.abspath(__file__))
    yield os.path.normpath(os.path.join(here, "..", "..", CONFIG_FILENAME))


def load_db_config() -> dict:
    values = dict(_DEFAULTS)

    for path in _config_paths():
        try:
            if os.path.isfile(path):
                cp = configparser.ConfigParser()
                cp.read(path, encoding="utf-8")
                if cp.has_section("database"):
                    for k in _KEYS:
                        if cp.has_option("database", k):
                            v = cp.get("database", k).strip()
                            if v:
                                values[k] = v
                break
        except Exception:
            pass

    # Les variables d'environnement priment.
    for k, env in _ENV.items():
        v = os.environ.get(env)
        if v and v.strip():
            values[k] = v.strip()

    missing = [k for k in ("host", "user", "password") if not values.get(k)]
    if missing:
        raise RuntimeError(
            "Configuration de la base de données incomplète : "
            + ", ".join(missing)
            + f".\nCréez un fichier « {CONFIG_FILENAME} » (voir "
            f"{CONFIG_FILENAME}.example) à côté de l'application, ou définissez "
            "les variables d'environnement DB_HOST / DB_USER / DB_PASSWORD."
        )
    return values


def database_url() -> str:
    c = load_db_config()
    return f"postgresql://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['name']}"
