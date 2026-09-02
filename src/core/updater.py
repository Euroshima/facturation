# src/core/updater.py
"""
Mise à jour depuis les releases GitHub (stdlib uniquement).

- Vérifie la dernière release du dépôt.
- Compare au __version__ local.
- Si plus récente : télécharge le nouvel .exe, le met en place à la fermeture
  de l'application (script .bat) puis redémarre.

Le dépôt étant privé, l'API GitHub exige un jeton en lecture seule. Il est lu,
dans l'ordre :
  1. variable d'environnement FACT_UPDATE_TOKEN
  2. fichier "update_token.txt" à côté de l'exe (ou du dossier courant en dev)
Le jeton n'est PAS stocké dans le code.

Journal : %TEMP%\\facturation_update.log
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import urllib.error

try:
    from tkinter import messagebox as mb
except Exception:
    mb = None

from .version import __version__, __app_name__

# ------------------ Configuration ------------------
GITHUB_OWNER = "Euroshima"
GITHUB_REPO = "facturation"
ASSET_SUFFIX = ".exe"
TIMEOUT = 20  # s pour les requêtes HTTP
TOKEN_FILENAME = "update_token.txt"
TOKEN_ENV = "FACT_UPDATE_TOKEN"
# --------------------------------------------------

LOG_PATH = os.path.join(tempfile.gettempdir(), "facturation_update.log")

_log = logging.getLogger("facturation.updater")
if not _log.handlers:
    _log.setLevel(logging.INFO)
    try:
        _h = logging.FileHandler(LOG_PATH, encoding="utf-8")
        _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        _log.addHandler(_h)
    except Exception:
        _log.addHandler(logging.NullHandler())


# ==========================================================================
#  Petites briques
# ==========================================================================

def _current_exe_path() -> str:
    """Chemin de l'exe en cours d'exécution (PyInstaller onefile)."""
    return sys.executable


def _staged_exe_path() -> str:
    """Emplacement du téléchargement, à côté de l'exe courant."""
    return os.path.join(os.path.dirname(_current_exe_path()), "Facturation.update.exe")


def _read_token() -> str:
    """Jeton GitHub en lecture seule : env var puis fichier à côté de l'exe."""
    tok = (os.environ.get(TOKEN_ENV) or "").strip()
    if tok:
        return tok
    seen = set()
    for d in (os.path.dirname(_current_exe_path()), os.getcwd()):
        if not d or d in seen:
            continue
        seen.add(d)
        try:
            p = os.path.join(d, TOKEN_FILENAME)
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8-sig") as f:
                    t = f.read().strip()
                if t:
                    return t
        except Exception:
            pass
    return ""


def _auth_headers(accept: str) -> dict:
    h = {
        "User-Agent": f"{__app_name__}-updater",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    tok = _read_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _version_tuple(v: str) -> tuple:
    """'v1.2.3' ou '1.2.3' -> (1, 2, 3) pour comparaison robuste."""
    v = (v or "").strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except Exception:
            break
    return tuple(parts or [0])


def _is_newer(remote: str, local: str) -> bool:
    return _version_tuple(remote) > _version_tuple(local)


def _fetch_latest_release() -> dict:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers=_auth_headers("application/vnd.github+json"))
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_asset(latest: dict):
    """Retourne (nom, url_api_asset) du premier asset .exe, ou None.

    On utilise l'URL API de l'asset (`url`) + Accept octet-stream : ça
    fonctionne aussi bien pour un dépôt public que privé.
    """
    for a in latest.get("assets") or []:
        name = a.get("name") or ""
        api_url = a.get("url") or ""
        if name.endswith(ASSET_SUFFIX) and api_url:
            return name, api_url
    return None


def _download(url: str, dest: str):
    """Téléchargement authentifié vers `dest`."""
    req = urllib.request.Request(url, headers=_auth_headers("application/octet-stream"))
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


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
    return False


# ==========================================================================
#  Remplacement de l'exe (partagé auto / manuel)
# ==========================================================================

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
    size = os.path.getsize(new_exe)
    _log.info("téléchargé %d octets -> %s", size, new_exe)
    if size < 1_000_000:
        raise RuntimeError("fichier téléchargé invalide (trop petit)")
    return new_exe


def _swap_and_restart(remote_tag: str, new_exe: str):
    """Sur le thread UI : prévient, lance le script de remplacement, coupe le
    process. En cas d'échec : nettoie et prévient l'utilisateur."""
    try:
        old_exe = _current_exe_path()
        _show_info(
            "Mise à jour",
            f"Mise à jour vers {remote_tag} téléchargée.\n"
            "L'application va se fermer puis redémarrer automatiquement.",
        )
        bat = _write_swap_script(os.getpid(), old_exe, new_exe)
        _log.info("lancement du script de bascule %s", bat)
        subprocess.Popen(
            ["cmd", "/c", bat],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
        os._exit(0)
    except Exception as e:
        _log.exception("échec de la bascule")
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
    """Vérifie la dernière release et, si plus récente, propose de l'installer.
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
        if not _read_token():
            _log.warning("aucun jeton (%s ou %s)", TOKEN_ENV, TOKEN_FILENAME)
            if ask_user:
                _show_error(
                    "Mise à jour",
                    "Jeton d'accès introuvable.\n\n"
                    f"Placez le fichier « {TOKEN_FILENAME} » à côté de l'application "
                    "(ou définissez la variable d'environnement "
                    f"{TOKEN_ENV}).",
                )
            return

        _log.info("vérification manuelle — version locale v%s", __version__)
        latest = _fetch_latest_release()
        remote_tag = latest.get("tag_name") or latest.get("name") or ""
        _log.info("release distante : %s", remote_tag)

        if not _is_newer(remote_tag, __version__):
            if ask_user:
                _show_info("Mise à jour", f"Vous êtes à jour.\nVersion actuelle : v{__version__}")
            return

        picked = _pick_asset(latest)
        if not picked:
            _log.error("aucun asset %s dans la release", ASSET_SUFFIX)
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

    except urllib.error.HTTPError as e:
        _log.exception("HTTP %s", e.code)
        if ask_user:
            hint = ""
            if e.code in (401, 403):
                hint = "\n\nLe jeton est invalide ou n'a pas l'accès en lecture au dépôt."
            elif e.code == 404:
                hint = "\n\nDépôt ou release introuvable (jeton sans accès ?)."
            _show_error("Mise à jour", f"Erreur HTTP {e.code}.{hint}")
    except Exception as e:
        _log.exception("échec vérification manuelle")
        if ask_user:
            _show_error("Mise à jour", f"Une erreur est survenue :\n{e}")


# ==========================================================================
#  Mise à jour AUTOMATIQUE au démarrage (packagé Windows uniquement)
# ==========================================================================

def _auto_update_worker(root):
    """Thread : vérifie + télécharge en arrière-plan, puis revient sur le
    thread UI pour fermer/relancer l'application."""
    try:
        if not _read_token():
            _log.info("auto-update ignorée : aucun jeton")
            return
        _log.info("auto-update — version locale v%s", __version__)
        latest = _fetch_latest_release()
        remote_tag = latest.get("tag_name") or latest.get("name") or ""
        _log.info("release distante : %s", remote_tag)
        if not _is_newer(remote_tag, __version__):
            _log.info("déjà à jour")
            return
        picked = _pick_asset(latest)
        if not picked:
            _log.error("aucun asset %s", ASSET_SUFFIX)
            return
        _, asset_url = picked
        new_exe = _stage_new_exe(asset_url)
    except Exception:
        _log.exception("auto-update : échec (silencieux pour l'utilisateur)")
        return

    _log.info("nouvelle version prête, bascule programmée")
    try:
        root.after(0, lambda: _swap_and_restart(remote_tag, new_exe))
    except Exception:
        _log.exception("auto-update : impossible de programmer la bascule")


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
    _log.info("=== démarrage %s v%s ===", __app_name__, __version__)
    # Nettoie un éventuel téléchargement resté d'une tentative précédente échouée
    try:
        leftover = _staged_exe_path()
        if os.path.exists(leftover):
            os.remove(leftover)
    except Exception:
        pass
    threading.Thread(target=_auto_update_worker, args=(root,), daemon=True).start()
