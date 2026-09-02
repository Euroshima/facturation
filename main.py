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
from core.db import init_db, find_or_create_client, try_connect
from core.dbconfig import database_url
from ui.app import App
from ui.db_config_dialog import show_db_config_dialog
from ui.appicon import apply_icon
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


def _db_reachable():
    """(ok, message)."""
    try:
        return try_connect(database_url())
    except Exception as e:
        return False, str(e)


def _ensure_db_configured(root):
    """Tant que la BDD n'est pas joignable, propose la fenêtre de config.
    Retourne True si on peut continuer, False si l'utilisateur abandonne."""
    ok, _ = _db_reachable()
    while not ok:
        if not show_db_config_dialog(root, first_run=True):
            return False
        ok, err = _db_reachable()
        if not ok and not messagebox.askretrycancel(
            f"{__app_name__} — base de données",
            f"Connexion toujours impossible :\n{err}",
        ):
            return False
    return True


def main():
    _improve_windows_ui()
    ensure_dirs()

    root = tk.Tk()
    root.withdraw()
    apply_icon(root)

    if not _ensure_db_configured(root):
        root.destroy()
        return

    try:
        init_db()
        ensure_my_info_in_db()
    except Exception as e:
        messagebox.showerror(
            f"{__app_name__} — base de données",
            f"Erreur d'initialisation de la base :\n\n{e}",
        )
        root.destroy()
        return

    root.deiconify()
    root.title(__app_name__)
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
