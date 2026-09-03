# main.py (à la racine du projet)
"""Point d'entrée de l'application Facturation.

Tout le démarrage est encadré par un garde-fou : la moindre erreur (import
manquant, DLL absente dans le paquet, etc.) est écrite dans
`facturation-error.log` (à côté de l'exe **et** dans %TEMP%) et affichée dans
une boîte de dialogue. Sans cela, en mode `--noconsole`, un double-clic sur
l'exe ne produirait strictement rien de visible.
"""

import datetime
import faulthandler
import os
import sys
import traceback

ERROR_LOG_NAME = "facturation-error.log"

# Gardé en global : le fichier doit rester ouvert tant que faulthandler écrit.
_FAULT_FILE = None


# ---------- Traçage du démarrage (désactivé par défaut, cf. core/debuglog) ----------
def _trace(msg):
    try:
        from core.debuglog import trace
        trace(msg)
    except Exception:
        pass


def _reset_boot_log():
    try:
        from core.debuglog import reset
        reset()
    except Exception:
        pass


# ---------- Sécurité --noconsole : sys.stdout / sys.stderr peuvent être None ----------
def _ensure_std_streams():
    """En mode `--noconsole`, `sys.stdout`/`sys.stderr` valent None et le
    moindre `print()` lève une AttributeError. On branche /dev/null (NUL)."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            try:
                setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
            except Exception:
                pass


def _error_log_paths():
    """Emplacements où écrire le rapport d'erreur (sans doublon)."""
    paths = []

    def _add(p):
        if p and p not in paths:
            paths.append(p)

    try:
        _add(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), ERROR_LOG_NAME))
    except Exception:
        pass
    try:
        import tempfile
        _add(os.path.join(tempfile.gettempdir(), ERROR_LOG_NAME))
    except Exception:
        pass
    try:
        _add(os.path.join(os.path.expanduser("~"), ERROR_LOG_NAME))
    except Exception:
        pass
    return paths


def _enable_faulthandler():
    """Active faulthandler vers un fichier (les crashs natifs y atterrissent)."""
    global _FAULT_FILE
    try:
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "facturation-faulthandler.log")
        _FAULT_FILE = open(path, "a", encoding="utf-8")
        faulthandler.enable(file=_FAULT_FILE, all_threads=True)
    except Exception:
        try:
            faulthandler.enable()
        except Exception:
            pass


def _startup_report(exc: BaseException) -> str:
    """Texte complet du rapport d'erreur de démarrage."""
    lines = [
        "=" * 72,
        f"Erreur au démarrage — {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
        "=" * 72,
        f"Python     : {sys.version}",
        f"Exécutable : {getattr(sys, 'executable', '?')}",
        f"Gelé (exe) : {getattr(sys, 'frozen', False)}",
        f"_MEIPASS   : {getattr(sys, '_MEIPASS', '(aucun)')}",
        f"Plateforme : {sys.platform}",
        f"Répertoire : {os.getcwd()}",
        "",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "",
        "sys.path :",
    ]
    lines += [f"  - {p}" for p in sys.path]
    lines.append("")
    return "\n".join(lines)


def _report_startup_failure(exc: BaseException):
    """Écrit le rapport dans tous les emplacements possibles puis l'affiche."""
    report = _startup_report(exc)
    written = []
    for path in _error_log_paths():
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(report)
            written.append(path)
        except Exception:
            continue

    # Dernier recours : la console si elle existe.
    try:
        sys.stderr.write(report)
    except Exception:
        pass

    # Boîte de dialogue si tkinter est disponible.
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        where = "\n".join(written) if written else "(aucun journal n'a pu être écrit)"
        messagebox.showerror(
            "Hytris Facturation — erreur au démarrage",
            "L'application n'a pas pu démarrer.\n\n"
            f"{type(exc).__name__} : {exc}\n\n"
            "Détails complets dans :\n"
            f"{where}",
        )
        root.destroy()
    except Exception:
        pass


# ---------- Bootstrapping du sys.path pour trouver src/core, src/ui, src/pdf ----------
def _bootstrap_sys_path():
    """
    Rendez les imports `core.*`, `ui.*`, `pdf.*` robustes :
    - en dev: on ajoute <project_root>/src
    - en .exe (PyInstaller): on tente d'abord _MEIPASS, sinon le dossier de l'exécutable
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


# ---------- Application ----------
def ensure_dirs():
    from core.settings import PDF_FOLDER
    os.makedirs(PDF_FOLDER, exist_ok=True)


def ensure_my_info_in_db():
    from core.settings import MY_INFO
    from core.db import find_or_create_client

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
        from core.db import try_connect
        from core.dbconfig import database_url
        return try_connect(database_url())
    except Exception as e:
        return False, str(e)


def _ensure_db_configured(root):
    """Tant que la BDD n'est pas joignable, propose la fenêtre de config.
    Retourne True si on peut continuer, False si l'utilisateur abandonne."""
    from tkinter import messagebox
    from ui.db_config_dialog import show_db_config_dialog
    from core.version import __app_name__

    _trace("_db_reachable()…")
    ok, msg = _db_reachable()
    _trace(f"_db_reachable -> {ok}")
    while not ok:
        _trace("affichage fenêtre config BDD")
        if not show_db_config_dialog(root, first_run=True):
            _trace("config BDD annulée")
            return False
        _trace("fenêtre config fermée, nouveau test")
        ok, err = _db_reachable()
        _trace(f"_db_reachable -> {ok}")
        if not ok and not messagebox.askretrycancel(
            f"{__app_name__} — base de données",
            f"Connexion toujours impossible :\n{err}",
        ):
            return False
    return True


def main():
    _trace("main() début")
    import tkinter as tk
    from tkinter import ttk, messagebox
    _trace("tkinter importé")

    from core.db import init_db
    _trace("core.db importé")
    from ui.app import App
    _trace("ui.app importé")
    from ui.appicon import apply_icon
    from core.version import __app_name__
    _trace("imports projet OK")

    _improve_windows_ui()
    ensure_dirs()
    _trace("ensure_dirs OK")

    root = tk.Tk()
    _trace("tk.Tk() créé")
    root.title(__app_name__)
    root.geometry("1200x800")
    apply_icon(root)
    _trace("apply_icon OK")
    root.withdraw()  # caché tant que l'appli n'est pas prête

    def _startup():
        """Séquence de démarrage exécutée DANS la boucle d'événements Tk :
        les fenêtres modales (config BDD…) ne fonctionnent de façon fiable
        qu'une fois mainloop() lancée."""
        _trace("_startup (dans mainloop)")
        try:
            _trace("_ensure_db_configured…")
            if not _ensure_db_configured(root):
                _trace("db non configurée -> fermeture")
                root.destroy()
                return
            _trace("db joignable")

            init_db()
            _trace("init_db OK")
            ensure_my_info_in_db()
            _trace("ensure_my_info_in_db OK")
        except Exception as e:
            _trace(f"ERREUR startup: {type(e).__name__}: {e}")
            try:
                messagebox.showerror(
                    f"{__app_name__} — base de données",
                    f"Erreur d'initialisation de la base :\n\n{e}",
                )
            except Exception:
                pass
            root.destroy()
            return

        style = ttk.Style()
        for theme in ("vista", "clam", "alt", "default"):
            if theme in style.theme_names():
                try:
                    style.theme_use(theme)
                    break
                except Exception:
                    continue

        _trace("construction App…")
        App(root)
        _trace("App construite")
        root.deiconify()
        root.lift()

    root.after(0, _startup)
    _trace("mainloop")
    root.mainloop()
    _trace("mainloop terminé")


def _console_pause():
    """Sur la variante avec console (Facturation-debug.exe), garde la fenêtre
    ouverte pour qu'on puisse lire l'erreur."""
    try:
        if sys.stdout is not None and sys.stdout.isatty():
            input("\n--- Appuyez sur Entrée pour fermer cette fenêtre ---\n")
    except Exception:
        pass


def _guarded_start():
    """Démarrage protégé : toute erreur devient un journal + une boîte d'alerte."""
    try:
        _ensure_std_streams()
        _enable_faulthandler()
        _bootstrap_sys_path()
        _reset_boot_log()
        _trace("guarded_start — streams/faulthandler/path OK")
        main()
        _trace("main() terminé normalement")
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — on veut vraiment tout attraper
        try:
            _trace(f"ERREUR: {type(exc).__name__}: {exc}")
        except Exception:
            pass
        try:
            _report_startup_failure(exc)
        except Exception:
            pass
        _console_pause()
        sys.exit(1)


if __name__ == "__main__":
    _guarded_start()
