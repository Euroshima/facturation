# src/core/updater.py
"""
Mise à jour depuis les releases GitHub (stdlib uniquement).

L'application est distribuée en **dossier** (PyInstaller `--onedir`) : la
release contient une archive `Facturation-<version>.zip` qui renferme le
dossier `Facturation/`. La mise à jour remplace donc tout le dossier, pas un
simple fichier .exe.

Déroulé :
  1. On interroge la dernière release du dépôt (public) et on compare au
     `__version__` local.
  2. On télécharge le .zip dans %TEMP% et on l'extrait dans un dossier voisin
     `Facturation.new` (à côté du dossier de l'application).
  3. Un script .bat attend la fermeture de l'application (par PID), supprime
     l'ancien dossier, met `Facturation.new` à sa place, relance l'exe puis se
     supprime lui-même.

Aucun jeton requis. Un jeton optionnel peut être fourni via FACT_UPDATE_TOKEN
ou "update_token.txt" à côté de l'exe (utile seulement pour contourner la
limite de débit anonyme de l'API GitHub).

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
import zipfile

try:
    from tkinter import messagebox as mb
except Exception:
    mb = None

from .version import __version__, __app_name__

# ------------------ Configuration ------------------
GITHUB_OWNER = "Euroshima"
GITHUB_REPO = "facturation"
ASSET_SUFFIX = ".zip"
APP_DIR_NAME = "Facturation"
APP_EXE_NAME = "Facturation.exe"
STAGED_DIR_NAME = "Facturation.new"
RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
TIMEOUT = 20  # s pour les requêtes HTTP
MIN_PACKAGE_SIZE = 1_000_000  # octets ; en dessous, l'archive est suspecte
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
    """Chemin de l'exe en cours d'exécution."""
    return sys.executable


def _app_dir() -> str:
    """Dossier de l'application (`.../Facturation` en mode --onedir)."""
    return os.path.dirname(os.path.abspath(_current_exe_path()))


def _parent_dir() -> str:
    """Dossier parent : c'est là qu'on prépare la nouvelle version."""
    return os.path.dirname(_app_dir())


def _staged_dir() -> str:
    """Dossier temporaire voisin contenant la nouvelle version extraite."""
    return os.path.join(_parent_dir(), STAGED_DIR_NAME)


def _cleanup_staged():
    """Supprime le dossier de préparation et son éventuel reliquat .tmp."""
    for path in (_staged_dir(), _staged_dir() + ".tmp"):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass


def _read_token() -> str:
    """Jeton GitHub en lecture seule : env var puis fichier à côté de l'exe."""
    tok = (os.environ.get(TOKEN_ENV) or "").strip()
    if tok:
        return tok
    seen = set()
    for d in (_app_dir(), os.getcwd()):
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
    """Retourne (nom, url_api_asset) du premier asset .zip, ou None.

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


def _console(prefix: str, title: str, msg: str):
    """Sortie console tolérante : avec `--noconsole`, sys.stdout vaut None."""
    try:
        out = getattr(sys, "stdout", None)
        if out is not None:
            out.write(f"{prefix} {title}: {msg}\n")
    except Exception:
        pass


def _show_info(title: str, msg: str):
    if mb:
        try:
            mb.showinfo(title, msg)
            return
        except Exception:
            pass
    _console("[INFO]", title, msg)


def _show_error(title: str, msg: str):
    if mb:
        try:
            mb.showerror(title, msg)
            return
        except Exception:
            pass
    _console("[ERREUR]", title, msg)


def _ask_yesno(title: str, msg: str) -> bool:
    if mb:
        try:
            return bool(mb.askyesno(title, msg))
        except Exception:
            return False
    return False


def _manual_download_hint() -> str:
    return (
        "Vous pouvez télécharger la dernière archive .zip manuellement :\n"
        f"{RELEASES_URL}\n\n"
        "Décompressez-la puis remplacez le dossier « Facturation »."
    )


# ==========================================================================
#  Préparation de la nouvelle version (dossier)
# ==========================================================================

def _tree_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except Exception:
                pass
    return total


def _find_app_root(extract_dir: str):
    """Trouve, dans l'archive extraite, le dossier contenant Facturation.exe."""
    if os.path.isfile(os.path.join(extract_dir, APP_EXE_NAME)):
        return extract_dir
    try:
        entries = [
            os.path.join(extract_dir, e)
            for e in os.listdir(extract_dir)
            if os.path.isdir(os.path.join(extract_dir, e))
        ]
    except Exception:
        return None
    for d in entries:
        if os.path.isfile(os.path.join(d, APP_EXE_NAME)):
            return d
    return None


def _stage_new_version(asset_url: str) -> str:
    """Télécharge le .zip dans %TEMP%, l'extrait dans `Facturation.new` à côté
    du dossier de l'application et vérifie sa cohérence.

    Retourne le chemin du dossier prêt à être mis en place.
    Lève une exception en cas de problème.
    """
    staged = _staged_dir()
    tmp_extract = staged + ".tmp"
    zip_path = os.path.join(tempfile.gettempdir(), "facturation_update.zip")

    _cleanup_staged()
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    except Exception:
        pass

    _log.info("téléchargement de l'archive -> %s", zip_path)
    _download(asset_url, zip_path)
    size = os.path.getsize(zip_path)
    _log.info("archive téléchargée : %d octets", size)
    if size < MIN_PACKAGE_SIZE:
        raise RuntimeError("archive téléchargée invalide (trop petite)")

    os.makedirs(tmp_extract, exist_ok=True)
    _log.info("extraction dans %s", tmp_extract)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(tmp_extract)

    root = _find_app_root(tmp_extract)
    if not root:
        raise RuntimeError(f"{APP_EXE_NAME} introuvable dans l'archive")

    # Normalisation : <parent>/Facturation.new/Facturation.exe doit exister.
    os.replace(root, staged)
    shutil.rmtree(tmp_extract, ignore_errors=True)
    try:
        os.remove(zip_path)
    except Exception:
        pass

    exe = os.path.join(staged, APP_EXE_NAME)
    if not os.path.isfile(exe):
        raise RuntimeError(f"{APP_EXE_NAME} manquant après extraction")
    total = _tree_size(staged)
    _log.info("version préparée dans %s (%d octets)", staged, total)
    if total < MIN_PACKAGE_SIZE:
        raise RuntimeError("contenu extrait invalide (trop petit)")
    return staged


def _write_swap_script(pid: int, app_dir: str, new_dir: str) -> str:
    """Écrit un .bat qui attend la fermeture de l'app (par PID), remplace le
    dossier de l'application par la nouvelle version, relance, puis se
    supprime lui-même."""
    bat = os.path.join(tempfile.gettempdir(), "facturation_update.bat")
    content = (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "PID={pid}"\r\n'
        f'set "APP={app_dir}"\r\n'
        f'set "NEW={new_dir}"\r\n'
        f'set "EXE={os.path.join(app_dir, APP_EXE_NAME)}"\r\n'
        ":wait\r\n"
        'tasklist /fi "PID eq %PID%" 2>nul | find "%PID%" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "    timeout /t 1 /nobreak >nul\r\n"
        "    goto wait\r\n"
        ")\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        'rmdir /s /q "%APP%" >nul 2>&1\r\n'
        'move "%NEW%" "%APP%" >nul 2>&1\r\n'
        'if not exist "%EXE%" (\r\n'
        "    timeout /t 3 /nobreak >nul\r\n"
        '    rmdir /s /q "%APP%" >nul 2>&1\r\n'
        '    move "%NEW%" "%APP%" >nul 2>&1\r\n'
        ")\r\n"
        'start "" "%EXE%"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w", encoding="ascii", errors="replace") as f:
        f.write(content)
    return bat


def _swap_and_restart(remote_tag: str, new_dir: str):
    """Sur le thread UI : prévient, lance le script de remplacement, coupe le
    process. En cas d'échec : nettoie et prévient l'utilisateur (sans quitter)."""
    try:
        app_dir = _app_dir()
        _show_info(
            "Mise à jour",
            f"Mise à jour vers {remote_tag} téléchargée.\n"
            "L'application va se fermer puis redémarrer automatiquement.",
        )
        bat = _write_swap_script(os.getpid(), app_dir, new_dir)
        _log.info("lancement du script de bascule %s (app=%s, new=%s)", bat, app_dir, new_dir)
        subprocess.Popen(
            ["cmd", "/c", bat],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
        os._exit(0)
    except Exception as e:
        _log.exception("échec de la bascule")
        _cleanup_staged()
        _show_error(
            "Mise à jour",
            f"La mise à jour a échoué :\n{e}\n\n"
            "L'application continue sur la version actuelle.\n\n"
            + _manual_download_hint(),
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
                "La mise à jour n'est disponible que dans la version installée.\n"
                f"Version actuelle : v{__version__}",
            )
        return
    if not sys.platform.startswith("win"):
        if ask_user:
            _show_info("Mise à jour", "Mise à jour non prise en charge sur cette plateforme.")
        return

    try:
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
                _show_error(
                    "Mise à jour",
                    "Aucune archive (.zip) trouvée dans la dernière release.\n\n"
                    + _manual_download_hint(),
                )
            return
        _, asset_url = picked

        if ask_user and not _ask_yesno(
            "Mise à jour disponible",
            f"Nouvelle version : {remote_tag}\n"
            f"Version actuelle : v{__version__}\n\n"
            "Télécharger et installer maintenant ?",
        ):
            return

        try:
            new_dir = _stage_new_version(asset_url)
        except Exception as e:
            _log.exception("échec de la préparation de la nouvelle version")
            _cleanup_staged()
            if ask_user:
                _show_error(
                    "Mise à jour",
                    f"La mise à jour a échoué :\n{e}\n\n" + _manual_download_hint(),
                )
            return

        _swap_and_restart(remote_tag, new_dir)

    except urllib.error.HTTPError as e:
        _log.exception("HTTP %s", e.code)
        if ask_user:
            hint = ""
            if e.code in (401, 403):
                hint = "\n\nAccès refusé par l'API GitHub (limite de débit ?)."
            elif e.code == 404:
                hint = "\n\nDépôt ou release introuvable."
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
        new_dir = _stage_new_version(asset_url)
    except Exception:
        _log.exception("auto-update : échec (silencieux pour l'utilisateur)")
        _cleanup_staged()
        return

    _log.info("nouvelle version prête, bascule programmée")
    try:
        root.after(0, lambda: _swap_and_restart(remote_tag, new_dir))
    except Exception:
        _log.exception("auto-update : impossible de programmer la bascule")
        _cleanup_staged()


def start_auto_update(root):
    """À appeler une fois au démarrage.

    Vérifie en arrière-plan qu'aucune release plus récente n'existe ; si oui,
    télécharge l'archive .zip, remplace le dossier de l'application à la
    fermeture et redémarre. N'agit qu'en mode packagé (`sys.frozen`) sous
    Windows ; sinon ne fait rien.
    """
    if not getattr(sys, "frozen", False):
        return
    if not sys.platform.startswith("win"):
        return
    _log.info("=== démarrage %s v%s ===", __app_name__, __version__)
    # Nettoie un éventuel dossier resté d'une tentative précédente échouée
    _cleanup_staged()
    threading.Thread(target=_auto_update_worker, args=(root,), daemon=True).start()
