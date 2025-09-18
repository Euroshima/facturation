import tkinter as tk
from tkinter import ttk, messagebox

from core.db import search_clients, get_invoice_with_items, get_conn

class TabClients(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        ct = ttk.Frame(self); ct.pack(fill="x", padx=6, pady=6)
        self.var_client_search = tk.StringVar()
        ttk.Entry(ct, textvariable=self.var_client_search, width=50).pack(side="left", padx=4)
        ttk.Button(ct, text="Rechercher", command=self._do_search).pack(side="left")
        ttk.Button(ct, text="Charger dans création", command=self._load_selected_into_form).pack(side="left", padx=6)

        self.tree = ttk.Treeview(
            self,
            columns=("id","prenom","nom","entreprise","email","telephone"),
            show="headings", height=14
        )
        for col, title, w, anchor in [
            ("id","ID",60,"center"),
            ("prenom","Prénom",120,"w"),
            ("nom","Nom",140,"w"),
            ("entreprise","Entreprise",220,"w"),
            ("email","Email",220,"w"),
            ("telephone","Téléphone",140,"w"),
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Double-1>", lambda e: self._load_selected_into_form())

    def _do_search(self):
        term = self.var_client_search.get().strip()
        rows = search_clients(term, limit=200)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            self.tree.insert(
                "", "end",
                values=(r["id"], r["prenom"] or "", r["nom"] or "", r["nom_entreprise"] or "", r["email"] or "", r["telephone"] or "")
            )

    def _load_selected_into_form(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("Client","Sélectionne un client.")
        cid = self.tree.item(sel[0], "values")[0]
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM clients WHERE id=?", (cid,))
        r = cur.fetchone()
        conn.close()
        if not r:
            return
        # Remplit l’onglet création
        c = self.controller
        c.var_c_prenom.set(r["prenom"] or "")
        c.var_c_nom.set(r["nom"] or "")
        c.var_c_ent.set(r["nom_entreprise"] or "")
        c.var_c_addr.set(r["adresse"] or "")
        c.var_c_email.set(r["email"] or "")
        c.var_c_tel.set(r["telephone"] or "")
        messagebox.showinfo("Client", "Client chargé dans l’onglet Création.")
