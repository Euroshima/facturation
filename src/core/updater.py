# src/core/updater.py
"""
Updater GitHub simple (stdlib only).

- Vérifie la dernière release GitHub.
- Compare au __version__ locale.
- Si plus récent, propose à l'utilisateur de télécharger.
- Télécharge l'asset .exe, le lance, puis ferme l'app (si packagée).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import urllib.error

try:
    # UI légère pour confirmations / erreurs
    import tkinter as tk
    from tkinter import messagebox as mb
except Exception:
    tk = None
    mb = None

from .version import __version__, __app_name__

# ------------------ CONFIG À PERSONNALISER ------------------
GITHUB_OWNER = "Euroshima"
GITHUB_REPO = "facturation"
# On prendra l'asset .exe de la release (premier qui correspond)
ASSET_SUFFIX = ".exe"
TIMEOUT = 15  # s pour les requêtes HTTP
# ------------------------------------------------------------


def _version_tuple(v: str) -> tuple:
    """Transforme 'v1.2.3' ou '1.2.3' -> (1,2,3) pour comparaison robuste."""
    v = (v or "").strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except Exception:
            # ignore morceaux non numériques (ex: rc1)
            break
    return tuple(parts or [0])


def _is_newer(remote: str, local: str) -> bool:
    return _version_tuple(remote) > _version_tuple(local)


def _fetch_latest_release() -> dict | None:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": f"{__app_name__}-updater"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        if resp.status != 200:
            return None
        data = resp.read()
        return json.loads(data.decode("utf-8"))


def _pick_asset(latest: dict) -> tuple[str, str] | None:
    """Retourne (name, download_url) de l'asset .exe à télécharger."""
    assets = latest.get("assets") or []
    for a in assets:
        name = a.get("name") or ""
        dl = a.get("browser_download_url") or ""
        if name.endswith(ASSET_SUFFIX) and dl:
            return name, dl
    return None


def _download(url: str, dest: str):
    # simple download (bloquant) ; on pourrait ajouter une barre de progression plus tard
    urllib.request.urlretrieve(url, dest)


def _show_info(title: str, msg: str):
    if mb:
        mb.showinfo(title, msg)
    else:
        print(f"[INFO] {title}: {msg}")


def _show_error(title: str, msg: str):
    if mb:
        mb.showerror(title, msg)
    else:
        print(f"[ERREUR] {title}: {msg}")


def _ask_yesno(title: str, msg: str) -> bool:
    if mb:
        return mb.askyesno(title, msg)
    # fallback console
    print(f"{title}: {msg} [y/N] ", end="")
    try:
        return input().strip().lower().startswith("y")
    except Exception:
        return False


# ==========================================================================
#  Mécanisme de remplacement de l'exe (partagé auto / manuel)
# ==========================================================================

def _current_exe_path() -> str:
    """Chemin de l'exe en cours d'exécution (PyInstaller onefile)."""
    return sys.executable


def _staged_exe_path() -> str:
    """Emplacement du téléchargement, à côté de l'exe courant."""
    return os.path.join(os.path.dirname(_current_exe_path()), "Facturation.update.exe")


def _write_swap_script(pid: int, old_exe: str, new_exe: str) -> str:
    """Écrit un .bat qui attend la fermeture de l'app (par PID), remplace
    l'exe par la nouvelle version, relance, puis se supprime lui-même."""
    bat = os.path.join(tempfile.gettempdir(), "facturation_update.bat")
    content = (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "PID={pid}"\r\n'
        f'set "OLD={old_exe}"\r\n'
        f'set "NEW={new_exe}"\r\n'
        ":wait\r\n"
        'tasklist /fi "PID eq %PID%" 2>nul | find "%PID%" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "    timeout /t 1 /nobreak >nul\r\n"
        "    goto wait\r\n"
        ")\r\n"
        'move /y "%NEW%" "%OLD%" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "    timeout /t 2 /nobreak >nul\r\n"
        '    move /y "%NEW%" "%OLD%" >nul 2>&1\r\n'
        ")\r\n"
        'start "" "%OLD%"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w", encoding="ascii", errors="replace") as f:
        f.write(content)
    return bat


def _stage_new_exe(asset_url: str) -> str:
    """Télécharge le nouvel exe à côté de l'actuel. Retourne son chemin.
    Lève une exception si le téléchargement échoue ou paraît invalide."""
    new_exe = _staged_exe_path()
    _download(asset_url, new_exe)
    if os.path.getsize(new_exe) < 1_000_000:
        raise RuntimeError("fichier téléchargé invalide")
    return new_exe


def _swap_and_restart(remote_tag: str, new_exe: str):
    """À exécuter sur le thread UI : prévient, lance le script de remplacement
    puis coupe le process. En cas d'échec, nettoie et prévient l'utilisateur."""
    try:
        old_exe = _current_exe_path()
        _show_info(
            "Mise à jour",
            f"Mise à jour vers {remote_tag} téléchargée.\n"
            "L'application va se fermer puis redémarrer automatiquement.",
        )
        _write_swap_script(os.getpid(), old_exe, new_exe)
        bat = os.path.join(tempfile.gettempdir(), "facturation_update.bat")
        subprocess.Popen(
            ["cmd", "/c", bat],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
        os._exit(0)
    except Exception as e:
        try:
            if os.path.exists(new_exe):
                os.remove(new_exe)
        except Exception:
            pass
        _show_error(
            "Mise à jour",
            f"La mise à jour a échoué :\n{e}\n\n"
            "L'application continue sur la version actuelle.",
        )


# ==========================================================================
#  Vérification MANUELLE (menu Aide)
# ==========================================================================

def check_and_maybe_update(ask_user: bool = True):
    """Vérifie la dernière release GitHub et, si plus récente, propose de
    l'installer (téléchargement + remplacement de l'exe + redémarrage).
    Appelée depuis le thread UI."""
    if not getattr(sys, "frozen", False):
        if ask_user:
            _show_info(
                "Mise à jour",
                "La mise à jour n'est disponible que dans la version installée (.exe).\n"
                f"Version actuelle : v{__version__}",
            )
        return
    if not sys.platform.startswith("win"):
        if ask_user:
            _show_info("Mise à jour", "Mise à jour non prise en charge sur cette plateforme.")
        return

    try:
        latest = _fetch_latest_release()
        if not latest:
            if ask_user:
                _show_error("Mise à jour", "Impossible de récupérer la dernière version.")
            return

        remote_tag = latest.get("tag_name") or latest.get("name") or ""
        if not _is_newer(remote_tag, __version__):
            if ask_user:
                _show_info("Mise à jour", f"Vous êtes à jour.\nVersion actuelle : v{__version__}")
            return

        picked = _pick_asset(latest)
        if not picked:
            if ask_user:
                _show_error("Mise à jour", "Aucun binaire (.exe) trouvé dans la dernière release.")
            return
        _, asset_url = picked

        if ask_user and not _ask_yesno(
            "Mise à jour disponible",
            f"Nouvelle version : {remote_tag}\n"
            f"Version actuelle : v{__version__}\n\n"
            "Télécharger et installer maintenant ?",
        ):
            return

        new_exe = _stage_new_exe(asset_url)
        _swap_and_restart(remote_tag, new_exe)

    except Exception as e:
        if ask_user:
            _show_error("Mise à jour", f"Une erreur est survenue :\n{e}")


# ==========================================================================
#  Mise à jour AUTOMATIQUE au démarrage (packagé Windows uniquement)
# ==========================================================================

def _auto_update_worker(root):
    """Thread : vérifie + télécharge en arrière-plan, puis revient sur le
    thread UI pour fermer/relancer l'application."""
    try:
        latest = _fetch_latest_release()
        if not latest:
            return
        remote_tag = latest.get("tag_name") or latest.get("name") or ""
        if not _is_newer(remote_tag, __version__):
            return
        picked = _pick_asset(latest)
        if not picked:
            return
        _, asset_url = picked
        new_exe = _stage_new_exe(asset_url)
    except Exception:
        # Hors ligne, release inaccessible, dossier non inscriptible… :
        # on ne dérange pas l'utilisateur, l'app continue normalement.
        return

    try:
        root.after(0, lambda: _swap_and_restart(remote_tag, new_exe))
    except Exception:
        pass


def start_auto_update(root):
    """À appeler une fois au démarrage.

    Vérifie en arrière-plan qu'aucune release plus récente n'existe ; si oui,
    télécharge le nouvel .exe, le met en place à la fermeture et redémarre.
    N'agit qu'en mode packagé (`sys.frozen`) sous Windows ; sinon ne fait rien.
    """
    if not getattr(sys, "frozen", False):
        return
    if not sys.platform.startswith("win"):
        return
    # Nettoie un éventuel téléchargement resté d'une tentative précédente échouée
    try:
        leftover = _staged_exe_path()
        if os.path.exists(leftover):
            os.remove(leftover)
    except Exception:
        pass
    threading.Thread(target=_auto_update_worker, args=(root,), daemon=True).start()
