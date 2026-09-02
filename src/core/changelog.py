# src/core/changelog.py — chargement du journal des versions (CHANGELOG.md)
import os
import sys

_FALLBACK = "Journal des versions indisponible."


def _candidate_paths():
    # 1) Bundle PyInstaller (--add-data "CHANGELOG.md;.")
    base = getattr(sys, "_MEIPASS", None)
    if base:
        yield os.path.join(base, "CHANGELOG.md")
    # 2) À côté de l'exe / du CWD
    yield os.path.join(os.path.dirname(sys.executable), "CHANGELOG.md")
    yield os.path.join(os.getcwd(), "CHANGELOG.md")
    # 3) Racine du projet en dev : src/core/changelog.py -> ../../CHANGELOG.md
    here = os.path.dirname(os.path.abspath(__file__))
    yield os.path.normpath(os.path.join(here, "..", "..", "CHANGELOG.md"))


def load_changelog() -> str:
    for path in _candidate_paths():
        try:
            if path and os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip() or _FALLBACK
        except Exception:
            continue
    return _FALLBACK
