# src/ui/dialog_util.py — helpers communs pour les fenêtres modales
"""
Sous Windows, une Toplevel « transient » d'un root masqué peut devenir
invisible tout en bloquant. Ces helpers rendent la fenêtre réellement
visible sans aucun appel bloquant (pas de wait_visibility).
"""


def center_on_screen(win, default_w=480, default_h=360):
    try:
        win.update_idletasks()
    except Exception:
        pass
    try:
        w = win.winfo_reqwidth() or default_w
        h = win.winfo_reqheight() or default_h
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 4)}")
    except Exception:
        pass


def make_visible(win):
    center_on_screen(win)
    try:
        win.deiconify()
    except Exception:
        pass
    try:
        win.lift()
    except Exception:
        pass
    try:
        win.attributes("-topmost", True)
        win.after(500, lambda: _safe(win.attributes, "-topmost", False))
    except Exception:
        pass
    try:
        win.focus_force()
    except Exception:
        pass
    _grab_later(win)


def _grab_later(win, tries=0):
    try:
        win.grab_set()
    except Exception:
        if tries < 10:
            win.after(100, lambda: _grab_later(win, tries + 1))


def _safe(fn, *a):
    try:
        fn(*a)
    except Exception:
        pass
