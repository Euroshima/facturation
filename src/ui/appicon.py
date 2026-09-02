# src/ui/appicon.py — applique l'icône Hytris à la fenêtre
import os
import sys
import tkinter as tk


def _assets_dir():
    # Bundle PyInstaller (--add-data "assets;assets")
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "assets")
        if os.path.isdir(p):
            return p
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "assets"))


def apply_icon(root: tk.Misc):
    """Icône de fenêtre / barre des tâches. Silencieux si les fichiers manquent."""
    assets = _assets_dir()

    # Windows : .ico multi-tailles (titre + barre des tâches)
    ico = os.path.join(assets, "hytris.ico")
    if sys.platform.startswith("win") and os.path.isfile(ico):
        try:
            root.iconbitmap(default=ico)
        except Exception:
            pass

    # Multi-plateforme : PNG via iconphoto
    imgs = []
    for name in ("hytris-32.png", "hytris-64.png", "hytris-128.png", "hytris.png"):
        path = os.path.join(assets, name)
        if os.path.isfile(path):
            try:
                imgs.append(tk.PhotoImage(file=path, master=root))
            except Exception:
                pass
    if imgs:
        try:
            root.iconphoto(True, *imgs)
            # garder une référence pour éviter le GC
            root._app_icons = imgs
        except Exception:
            pass
