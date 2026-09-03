# src/core/updater.py
"""
Mise à jour depuis les releases GitHub (stdlib uniquement).

- Vérifie la dernière release du dépôt (public).
- Compare au __version__ local.
- Si plus récente : télécharge le nouvel .exe, le met en place à la fermeture
  de l'application (script .bat) puis redémarre.

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
    """Retourne (nom, url_api_asset) de l'exe de l'application, ou None.

    On ignore la variante « debug » et on privilégie « Facturation.exe ».
    URL API de l'asset (`url`) + Accept octet-stream : marche dépôt public
    comme privé.
    """
    candidates = []
    for a in latest.get("assets") or []:
        name = a.get("name") or ""
        api_url = a.get("url") or ""
        if not api_url or not name.lower().endswith(ASSET_SUFFIX):
            continue
        if "debug" in name.lower():
            continue
        candidates.append((name, api_url))
    if not candidates:
        return None
    for name, api_url in candidates:
        if name.lower() == "facturation.exe":
            return name, api_url
    return candidates[0]


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
    """Écrit un .bat qui : attend la fin de l'app (par PID), attend que l'exe
    soit déverrouillé, le remplace par la nouvelle version, relance, se supprime.

    IMPORTANT : `timeout` ne fonctionne pas quand le .bat tourne sans console
    (processus détaché) -> on temporise avec `ping`. Et le .exe reste verrouillé
    quelques secondes après la fermeture (bootloader onefile / antivirus /
    OneDrive) -> on réessaie en boucle.
    """
    bat = os.path.join(tempfile.gettempdir(), "facturation_update.bat")
    log = os.path.join(tempfile.gettempdir(), "facturation_update_bat.log")
    content = (
        "@echo off\r\n"
        "setlocal enabledelayedexpansion\r\n"
        f'set "PID={pid}"\r\n'
        f'set "OLD={old_exe}"\r\n'
        f'set "NEW={new_exe}"\r\n'
        f'set "LOG={log}"\r\n'
        'echo [%date% %time%] debut PID=%PID% > "%LOG%"\r\n'
        'echo   OLD=%OLD% >> "%LOG%"\r\n'
        'echo   NEW=%NEW% >> "%LOG%"\r\n'
        # 1) attendre la fin du process applicatif (borné : ~60 s max)
        "set /a w=0\r\n"
        ":wait\r\n"
        'tasklist /fi "PID eq %PID%" 2>nul | find "%PID%" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "    set /a w+=1\r\n"
        "    if !w! lss 30 (\r\n"
        "        ping -n 3 127.0.0.1 >nul\r\n"
        "        goto wait\r\n"
        "    )\r\n"
        '    echo [%date% %time%] ATTENTE ABANDONNEE (w=!w!) >> "%LOG%"\r\n'
        ")\r\n"
        'echo [%date% %time%] process termine (w=!w!) >> "%LOG%"\r\n'
        'del "%OLD%.old" >nul 2>&1\r\n'
        # 2) libérer l'ancien exe : le RENOMMER d'abord (réussit souvent même
        #    quand la suppression échoue sur un fichier encore verrouillé),
        #    sinon tenter la suppression ; on réessaie (~90 s max)
        "set /a n=0\r\n"
        ":swap\r\n"
        'move /y "%OLD%" "%OLD%.old" >nul 2>&1\r\n'
        'if exist "%OLD%" del "%OLD%" >nul 2>&1\r\n'
        'if exist "%OLD%" (\r\n'
        "    set /a n+=1\r\n"
        "    if !n! lss 30 (\r\n"
        "        ping -n 4 127.0.0.1 >nul\r\n"
        "        goto swap\r\n"
        "    )\r\n"
        '    echo [%date% %time%] ECHEC liberation de OLD (n=!n!) >> "%LOG%"\r\n'
        ")\r\n"
        # 3) mettre la nouvelle version en place
        'move /y "%NEW%" "%OLD%" >nul 2>&1\r\n'
        'echo [%date% %time%] apres move : essais=!n! >> "%LOG%"\r\n'
        'if exist "%OLD%" (echo   OLD present >> "%LOG%") else (echo   OLD ABSENT >> "%LOG%")\r\n'
        'if exist "%NEW%" (echo   NEW encore present >> "%LOG%") else (echo   NEW consomme >> "%LOG%")\r\n'
        'del "%OLD%.old" >nul 2>&1\r\n'
        # 4) relancer : si le move a réussi, %NEW% a disparu -> on lance %OLD%
        #    (nouveau contenu). Sinon repli sur %NEW%.
        'if not exist "%NEW%" (\r\n'
        '    echo [%date% %time%] lancement %OLD% >> "%LOG%"\r\n'
        '    start "" "%OLD%"\r\n'
        ") else (\r\n"
        '    echo [%date% %time%] REPLI lancement %NEW% >> "%LOG%"\r\n'
        '    start "" "%NEW%"\r\n'
        ")\r\n"
        'echo [%date% %time%] termine >> "%LOG%"\r\n'
        'del "%~f0"\r\n'
    )
    # cmd.exe lit un .bat dans le codepage ANSI (cp1252 sur Windows FR) : on
    # écrit dans cet encodage pour que les chemins accentués passent.
    with open(bat, "w", encoding="cp1252", errors="replace", newline="") as f:
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
        # CREATE_NO_WINDOW : pas de fenêtre console qui traîne.
        # CREATE_NEW_PROCESS_GROUP + BREAKAWAY : le .bat survit à notre sortie.
        flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                 | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000))
        try:
            subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True)
        except OSError:
            # CREATE_BREAKAWAY_FROM_JOB peut être refusé selon le job object
            flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                     | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True)
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

def check_and_maybe_update(ask_user: bool = True, show_errors=None):
    """Vérifie la dernière release et, si plus récente, propose de l'installer.
    Appelée depuis le thread UI.

    ask_user   : afficher les infos (« à jour », confirmation avant install).
    show_errors: afficher les erreurs (défaut = ask_user). Mettre True quand
                 l'utilisateur a déjà confirmé ailleurs (pop-up de démarrage).
    """
    if show_errors is None:
        show_errors = ask_user
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
            if show_errors:
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
        if show_errors:
            hint = ""
            if e.code in (401, 403):
                hint = "\n\nAccès refusé par l'API GitHub (limite de débit ?)."
            elif e.code == 404:
                hint = "\n\nDépôt ou release introuvable."
            _show_error("Mise à jour", f"Erreur HTTP {e.code}.{hint}")
    except Exception as e:
        _log.exception("échec vérification manuelle")
        if show_errors:
            _show_error("Mise à jour", f"Une erreur est survenue :\n{e}")


# ==========================================================================
#  Notification « nouvelle version disponible » (au démarrage, non bloquant)
# ==========================================================================

def latest_version_available():
    """Interroge la dernière release. Retourne la version distante (ex.
    '1.2.5') si elle est plus récente que la version locale, sinon None.
    Lève en cas d'erreur réseau (à l'appelant de l'ignorer)."""
    latest = _fetch_latest_release()
    tag = latest.get("tag_name") or latest.get("name") or ""
    if _is_newer(tag, __version__):
        return tag.lstrip("vV")
    return None


def check_for_update_async(on_available):
    """Vérifie en arrière-plan (thread daemon) si une version plus récente
    existe. Si oui, appelle `on_available(version)` — DEPUIS LE THREAD DE FOND :
    l'appelant doit re-poster sur le thread UI (root.after). Silencieux sinon.
    Ne fait rien hors mode packagé.
    """
    if not getattr(sys, "frozen", False):
        return

    def _work():
        try:
            v = latest_version_available()
            if v:
                _log.info("nouvelle version disponible : %s", v)
                on_available(v)
        except Exception:
            _log.exception("check_for_update_async")

    threading.Thread(target=_work, daemon=True).start()
