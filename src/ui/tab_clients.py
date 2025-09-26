import tkinter as tk
from tkinter import ttk, messagebox
from core.db import search_clients, get_conn, update_client
import psycopg2
import psycopg2.extras

class TabClients(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        ct = ttk.Frame(self)
        ct.pack(fill="x", padx=6, pady=6)

        self.var_client_search = tk.StringVar()
        ttk.Entry(ct, textvariable=self.var_client_search, width=40).pack(side="left", padx=4)
        ttk.Button(ct, text="Rechercher", command=self._do_search).pack(side="left")
        ttk.Button(ct, text="Charger dans création", command=self._load_selected_into_form).pack(side="left", padx=6)
        ttk.Button(ct, text="Éditer la sélection", command=self._edit_selected_client).pack(side="left", padx=6)

        self.tree = ttk.Treeview(self, columns=("id","prenom","nom","entreprise","email","telephone"), show="headings", height=14)
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

        # Menu contextuel clic droit
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Modifier", command=self._edit_selected_client)
        self.tree.bind("<Button-3>", self._on_right_click)

    # ---- Recherche clients ----
    def _do_search(self):
        term = self.var_client_search.get().strip()
        rows = search_clients(term, limit=200)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            self.tree.insert("", "end", values=(
                r["id"], r["prenom"] or "", r["nom"] or "", r["nom_entreprise"] or "", r["email"] or "", r["telephone"] or ""
            ))

    # ---- Charger client sélectionné dans l'onglet création ----
    def _load_selected_into_form(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("Client","Sélectionne un client.")
        cid = self.tree.item(sel[0], "values")[0]
        conn = get_conn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT * FROM clients WHERE id=%s", (cid,))
            r = cur.fetchone()
        finally:
            conn.close()
        if not r:
            return
        c = self.controller
        c.var_c_prenom.set(r["prenom"] or "")
        c.var_c_nom.set(r["nom"] or "")
        c.var_c_ent.set(r["nom_entreprise"] or "")
        c.var_c_addr.set(r["adresse"] or "")
        c.var_c_email.set(r["email"] or "")
        c.var_c_tel.set(r["telephone"] or "")
        messagebox.showinfo("Client", "Client chargé dans l’onglet Création.")

    # ---- Clic droit ----
    def _on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)

    # ---- Editer client sélectionné ----
    def _edit_selected_client(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showinfo("Client", "Sélectionne un client à éditer.")
        cid = self.tree.item(sel[0], "values")[0]

        conn = get_conn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT * FROM clients WHERE id=%s", (cid,))
            client = cur.fetchone()
        finally:
            conn.close()
        if not client:
            return

        # Création modal
        modal = tk.Toplevel(self)
        modal.title("Modifier client")
        modal.grab_set()

        labels = ["Prénom:", "Nom:", "Entreprise:", "Adresse:", "Email:", "Téléphone:"]
        vars_ = [
            tk.StringVar(value=client["prenom"]),
            tk.StringVar(value=client["nom"]),
            tk.StringVar(value=client["nom_entreprise"]),
            tk.StringVar(value=client["adresse"]),
            tk.StringVar(value=client["email"]),
            tk.StringVar(value=client["telephone"]),
        ]

        for i, label in enumerate(labels):
            tk.Label(modal, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            tk.Entry(modal, textvariable=vars_[i], width=40).grid(row=i, column=1, padx=5, pady=3)

        def save():
            # Mise à jour DB
            update_client(
                cid,
                prenom=vars_[0].get(),
                nom=vars_[1].get(),
                nom_entreprise=vars_[2].get(),
                adresse=vars_[3].get(),
                email=vars_[4].get(),
                telephone=vars_[5].get()
            )
            # Mise à jour Treeview
            self.tree.item(sel[0], values=(
                cid, vars_[0].get(), vars_[1].get(), vars_[2].get(), vars_[4].get(), vars_[5].get()
            ))
            modal.destroy()
            messagebox.showinfo("Client", "Client mis à jour avec succès.")

        tk.Button(modal, text="Enregistrer", command=save).grid(row=len(labels), column=0, columnspan=2, pady=10)
