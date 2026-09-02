# main.py (à la racine du projet)
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# ---------- Bootstrapping du sys.path pour trouver src/core, src/ui, src/pdf ----------
def _bootstrap_sys_path():
    """
    Rendez les imports `core.*`, `ui.*`, `pdf.*` robustes :
    - en dev: on ajoute <project_root>/src
    - en .exe (PyInstaller onefile): on tente d'abord _MEIPASS, sinon le dossier de l'exécutable
    """
    try:
        import core  # noqa: F401
        return  # déjà importable -> rien à faire
    except Exception:
        pass

    # Base selon contexte (PyInstaller -> _MEIPASS ou dossier de l'exe ; sinon dossier du fichier)
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(base, "src"),
        os.path.join(os.path.dirname(sys.executable), "src") if getattr(sys, "frozen", False) else None,
    ]

    for p in candidates:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)

_bootstrap_sys_path()

# ---------- Imports projet (après bootstrap) ----------
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
        from ctypes import windll  # type: ignore
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main():
    _improve_windows_ui()
    ensure_dirs()

    root = tk.Tk()
    root.withdraw()

    try:
        init_db()
        ensure_my_info_in_db()
    except Exception as e:
        messagebox.showerror(
            f"{__app_name__} — base de données",
            "Impossible de se connecter à la base de données.\n\n"
            f"{e}",
        )
        root.destroy()
        return

    root.deiconify()
    root.title(f"{__app_name__} (Tkinter)")
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
