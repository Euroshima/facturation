import re
import tkinter as tk


def _to_float(s):
    """Convertit une cellule en nombre si possible, sinon None."""
    s = re.sub(r"[^\d,.\-]", "", s or "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def make_sortable(tree, numeric_columns=None):
    """Rend les colonnes d'un ttk.Treeview triables par clic sur l'en-tête.

    Clic : tri croissant. Re-clic sur la même colonne : tri décroissant.
    Une flèche ▲/▼ indique la colonne et le sens du tri.
    `numeric_columns` force un tri numérique ; les autres colonnes sont
    triées numériquement seulement si toutes leurs valeurs sont des nombres.

    Attache `tree.reapply_sort()` : à rappeler après avoir repeuplé l'arbre
    pour conserver le tri et la flèche actifs.
    """
    numeric_columns = set(numeric_columns or ())
    base_titles = {c: tree.heading(c, "text") for c in tree["columns"]}
    state = {"col": None, "reverse": False}

    def sort_by(col, toggle=True):
        if toggle:
            reverse = not state["reverse"] if state["col"] == col else False
        else:
            reverse = state["reverse"]
        state.update(col=col, reverse=reverse)

        rows = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        vals = [v for v, _ in rows if (v or "").strip()]
        numeric = col in numeric_columns or (
            bool(vals) and all(_to_float(v) is not None for v in vals)
        )
        if numeric:
            rows.sort(key=lambda t: (_to_float(t[0]) is None, _to_float(t[0]) or 0.0),
                      reverse=reverse)
        else:
            rows.sort(key=lambda t: (t[0] or "").lower(), reverse=reverse)

        for idx, (_, iid) in enumerate(rows):
            tree.move(iid, "", idx)

        for c in tree["columns"]:
            arrow = "  ▼" if (c == col and reverse) else "  ▲" if c == col else ""
            tree.heading(c, text=base_titles[c] + arrow)

    def reapply_sort():
        if state["col"] is not None:
            sort_by(state["col"], toggle=False)

    for c in tree["columns"]:
        tree.heading(c, command=lambda c=c: sort_by(c))

    tree.reapply_sort = reapply_sort


class SuggestPopup(tk.Toplevel):
    """Popup simple d’autocomplétion pour Entry."""
    def __init__(self, parent_entry, on_select):
        super().__init__(parent_entry)
        self.withdraw()
        self.overrideredirect(True)
        self.listbox = tk.Listbox(self, height=8)
        self.listbox.pack(fill="both", expand=True)
        self.parent_entry = parent_entry
        self.on_select = on_select
        self.listbox.bind("<Double-1>", self._choose)
        self.listbox.bind("<Return>", self._choose)
        self.listbox.bind("<Escape>", lambda e: self.hide())

    def show(self, items):
        self.listbox.delete(0, tk.END)
        for t in items:
            self.listbox.insert(tk.END, t)
        if not items:
            return self.hide()
        x = self.parent_entry.winfo_rootx()
        y = self.parent_entry.winfo_rooty() + self.parent_entry.winfo_height()
        w = self.parent_entry.winfo_width()
        self.geometry(f"{w}x160+{x}+{y}")
        self.deiconify()
        self.lift()
        self.listbox.selection_clear(0, tk.END)
        if self.listbox.size():
            self.listbox.selection_set(0)

    def hide(self):
        self.withdraw()

    def _choose(self, *_):
        sel = self.listbox.curselection()
        if sel:
            self.on_select(self.listbox.get(sel[0]))
        self.hide()
