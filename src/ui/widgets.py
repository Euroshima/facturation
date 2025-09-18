import tkinter as tk

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
