# main.py (à la racine du projet)
import os
import sys
import tkinter as tk
from tkinter import ttk

# --- Ajouter src/ au PYTHONPATH ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.settings import MY_INFO, PDF_FOLDER
from core.db import init_db, find_or_create_client
from ui.app import App
from core.version import __version__, __app_name__


def ensure_dirs():
    os.makedirs(PDF_FOLDER, exist_ok=True)


def ensure_my_info_in_db():
    full_name = (MY_INFO.get("nom") or "").strip()
    parts = full_name.split()
    prenom = parts[0] if parts else ""
    nom = parts[-1] if parts else ""
    find_or_create_client(
        prenom=prenom,
        nom=nom,
        entreprise=(MY_INFO.get("nom_entreprise") or "").strip(),
        adresse=(MY_INFO.get("adresse") or "").strip(),
        email=(MY_INFO.get("email") or "").strip(),
        tel=(MY_INFO.get("telephone") or "").strip(),
    )


def _improve_windows_ui():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main():
    _improve_windows_ui()
    ensure_dirs()
    init_db()
    ensure_my_info_in_db()

    root = tk.Tk()
    root.title("Facturier (tkinter)")
    root.geometry("1200x800")

    style = ttk.Style()
    for theme in ("vista", "clam", "alt", "default"):
        if theme in style.theme_names():
            try:
                style.theme_use(theme)
                break
            except Exception:
                continue

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
