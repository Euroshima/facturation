# src/core/debuglog.py — trace de démarrage, désactivée par défaut
"""
`trace(msg)` n'écrit dans facturation-boot.log QUE si le debug est activé :
  - variable d'environnement FACT_DEBUG=1
  - ou fichier `debug.txt` à côté de l'exe
  - ou fichier `debug.txt` dans le dossier de config utilisateur

Ainsi, en usage normal, aucun fichier de log n'encombre le dossier.
(`facturation-error.log`, lui, n'est écrit qu'en cas de plantage réel.)
"""

import datetime
import os
import sys
import tempfile

BOOT_LOG_NAME = "facturation-boot.log"
_enabled = None


def enabled() -> bool:
    global _enabled
    if _enabled is not None:
        return _enabled
    val = False
    try:
        if (os.environ.get("FACT_DEBUG") or "").strip() not in ("", "0", "false", "False"):
            val = True
    except Exception:
        pass
    if not val:
        for d in (os.path.dirname(os.path.abspath(sys.executable)), _cfg_dir()):
            try:
                if d and os.path.isfile(os.path.join(d, "debug.txt")):
                    val = True
                    break
            except Exception:
                pass
    _enabled = val
    return val


def _cfg_dir():
    try:
        from core.appconfig import config_dir
        return config_dir()
    except Exception:
        return ""


def _paths():
    out = []
    try:
        out.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), BOOT_LOG_NAME))
    except Exception:
        pass
    try:
        out.append(os.path.join(tempfile.gettempdir(), BOOT_LOG_NAME))
    except Exception:
        pass
    return out


def reset():
    if not enabled():
        return
    for p in _paths():
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(f"=== démarrage {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
        except Exception:
            pass


def trace(msg):
    if not enabled():
        return
    line = f"{datetime.datetime.now():%H:%M:%S.%f} | {msg}\n"
    for p in _paths():
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
        except Exception:
            pass
    try:
        if sys.stdout is not None:
            sys.stdout.write(line)
            sys.stdout.flush()
    except Exception:
        pass
