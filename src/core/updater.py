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


def check_and_maybe_update(ask_user: bool = True):
    """
    Vérifie la dernière version GitHub et propose d'installer.
    - Si packagé (.exe PyInstaller) : lance le nouvel exe et ferme l'app.
    - Sinon : ouvre le dossier du fichier téléchargé.
    """
    try:
        latest = _fetch_latest_release()
        if not latest:
            if ask_user:
                _show_error("Mise à jour", "Impossible de récupérer la dernière version.")
            return

        remote_tag = latest.get("tag_name") or latest.get("name") or ""
        if not _is_newer(remote_tag, __version__):
            if ask_user:
                _show_info("Mise à jour", f"Aucune mise à jour disponible.\nVersion actuelle : v{__version__}")
            return

        # Trouver l'asset .exe
        picked = _pick_asset(latest)
        if not picked:
            if ask_user:
                _show_error("Mise à jour", "Aucun binaire (.exe) trouvé dans la dernière release.")
            return

        asset_name, asset_url = picked

        if not ask_user or _ask_yesno(
            "Mise à jour disponible",
            f"Nouvelle version trouvée : {remote_tag}\n"
            f"Version actuelle : v{__version__}\n\n"
            "Voulez-vous télécharger et installer maintenant ?"
        ):
            # Téléchargement vers un dossier temp
            dest = os.path.join(tempfile.gettempdir(), asset_name)
            try:
                _download(asset_url, dest)
            except urllib.error.URLError as e:
                _show_error("Mise à jour", f"Échec du téléchargement :\n{e}")
                return

            # Lance l'exe téléchargé
            try:
                if sys.platform.startswith("win"):
                    os.startfile(dest)  # type: ignore[attr-defined]
                else:
                    # Au cas où on build aussi pour d'autres plateformes
                    os.spawnlp(os.P_NOWAIT, "open" if sys.platform == "darwin" else "xdg-open", "open", dest)
            except Exception as e:
                _show_error("Mise à jour", f"Impossible de lancer l'installateur :\n{e}")
                return

            # Si l'app est packagée, on ferme l'appli pour laisser l'installateur faire son job
            if getattr(sys, "frozen", False):
                _show_info("Mise à jour", "L'installateur a été lancé. L'application va se fermer.")
                os._exit(0)  # arrêt immédiat du processus
            else:
                # En dev, on laisse l'appli ouverte et on ouvre le dossier
                try:
                    folder = os.path.dirname(dest)
                    if sys.platform.startswith("win"):
                        os.startfile(folder)  # type: ignore[attr-defined]
                    else:
                        os.spawnlp(os.P_NOWAIT, "open" if sys.platform == "darwin" else "xdg-open", "open", folder)
                except Exception:
                    pass
                _show_info("Mise à jour", f"Fichier téléchargé dans :\n{dest}")

    except Exception as e:
        if ask_user:
            _show_error("Mise à jour", f"Une erreur est survenue :\n{e}")


# ==========================================================================
#  Mise à jour AUTOMATIQUE au démarrage (packagé Windows uniquement)
# ==========================================================================

def _current_exe_path() -> str:
    """Chemin de l'exe en cours d'exécution (PyInstaller onefile)."""
    return sys.executable


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


def _auto_update_worker(root):
    """Exécuté dans un thread : vérifie + télécharge en arrière-plan, puis
    revient sur le thread UI pour fermer/relancer l'application."""
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

        old_exe = _current_exe_path()
        new_exe = os.path.join(os.path.dirname(old_exe), "Facturation.update.exe")
        _download(asset_url, new_exe)
        if os.path.getsize(new_exe) < 1_000_000:
            raise RuntimeError("fichier téléchargé invalide")
    except Exception:
        # Hors ligne, release inaccessible, dossier non inscriptible… :
        # on ne dérange pas l'utilisateur, l'app continue normalement.
        return

    def _finish():
        try:
            _show_info(
                "Mise à jour",
                f"Mise à jour vers {remote_tag} téléchargée.\n"
                "L'application va se fermer puis redémarrer automatiquement.",
            )
            bat = _write_swap_script(os.getpid(), old_exe, new_exe)
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
                f"La mise à jour automatique a échoué :\n{e}\n\n"
                "L'application continue sur la version actuelle.",
            )

    try:
        root.after(0, _finish)
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
        leftover = os.path.join(os.path.dirname(_current_exe_path()), "Facturation.update.exe")
        if os.path.exists(leftover):
            os.remove(leftover)
    except Exception:
        pass
    threading.Thread(target=_auto_update_worker, args=(root,), daemon=True).start()
