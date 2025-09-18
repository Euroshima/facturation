import os
import re
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from .settings import DB_FILE


# ---------- Connexion ----------
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Active les clés étrangères (au cas où)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ---------- Normalisation ----------
def _norm_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())

def _norm_email(s: str) -> str:
    return _norm_text(s)

def _norm_phone(s: str) -> str:
    if not s:
        return ""
    raw = s.strip()
    nums = re.sub(r"\D+", "", raw)
    if raw.startswith("+") and len(nums) >= 2:
        nums = "00" + nums[1:]
    return nums

# ---------- Déduplication interne (utilisée par init_db + callable à la demande) ----------
def _dedupe_clients_core(conn: sqlite3.Connection):
    """
    Garde, pour chaque identité logique, le client au plus petit id.
    Rattache les factures au 'keep_id' et supprime les doublons.
    Doit être appelée AVANT de créer l'index unique.
    """
    cur = conn.cursor()
    cur.execute("""
      WITH norm AS (
        SELECT
          id,
          lower(trim(coalesce(prenom,''))) AS p,
          lower(trim(coalesce(nom,''))) AS n,
          lower(trim(coalesce(nom_entreprise,''))) AS e,
          lower(trim(coalesce(email,''))) AS mail,
          replace(replace(replace(replace(coalesce(telephone,''),' ',''),'.',''),'-',''),'+','') AS tel
        FROM clients
      ),
      grp AS (
        SELECT p,n,e,mail,tel, MIN(id) AS keep_id, COUNT(*) AS cnt
        FROM norm
        GROUP BY p,n,e,mail,tel
        HAVING COUNT(*) > 1
      )
      SELECT g.keep_id, n.id AS dup_id
      FROM grp g
      JOIN norm n
        ON n.p=g.p AND n.n=g.n AND n.e=g.e AND n.mail=g.mail AND n.tel=g.tel
      WHERE n.id <> g.keep_id
    """)
    dups = cur.fetchall()
    if not dups:
        return

    for r in dups:
        keep_id, dup_id = r["keep_id"], r["dup_id"]
        # Rattache factures
        cur.execute("UPDATE invoices SET client_id=? WHERE client_id=?", (keep_id, dup_id))
        # Supprime doublon
        cur.execute("DELETE FROM clients WHERE id=?", (dup_id,))
    conn.commit()

def dedupe_clients():
    """Appel manuel possible depuis l'app pour nettoyer l'existant."""
    conn = get_conn()
    try:
        _dedupe_clients_core(conn)
    finally:
        conn.close()

# ---------- Schéma / Index ----------
def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS clients(
            id INTEGER PRIMARY KEY,
            prenom TEXT,
            nom TEXT,
            nom_entreprise TEXT,
            adresse TEXT,
            email TEXT,
            telephone TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices(
            id INTEGER PRIMARY KEY,
            facture_num TEXT UNIQUE,
            client_id INTEGER,
            date TEXT,
            subtotal REAL,
            tva REAL,
            total REAL,
            pdf_path TEXT,
            notes TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY,
            invoice_id INTEGER,
            description TEXT,
            qty REAL,
            price REAL,
            total REAL,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id)
        )
    """)
    conn.commit()

    # 1) Déduplication AVANT index unique (si la table existait déjà)
    _dedupe_clients_core(conn)

    # 2) Création de l'index unique logique — si ça échoue, on redédoublonne et on retente
    try:
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_identity
            ON clients(
              lower(trim(coalesce(prenom,''))),
              lower(trim(coalesce(nom,''))),
              lower(trim(coalesce(nom_entreprise,''))),
              lower(trim(coalesce(email,''))),
              replace(replace(replace(replace(coalesce(telephone,''),' ',''),'.',''),'-',''),'+','')
            )
        """)
        conn.commit()
    except sqlite3.IntegrityError:
        # Il reste des doublons très pathologiques -> on nettoie et on retente une fois
        _dedupe_clients_core(conn)
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_identity
            ON clients(
              lower(trim(coalesce(prenom,''))),
              lower(trim(coalesce(nom,''))),
              lower(trim(coalesce(nom_entreprise,''))),
              lower(trim(coalesce(email,''))),
              replace(replace(replace(replace(coalesce(telephone,''),' ',''),'.',''),'-',''),'+','')
            )
        """)
        conn.commit()

    conn.close()

# ---------- Utils ----------
def money(x):
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# ---------- Clients ----------
def save_client(prenom, nom, nom_entreprise, adresse, email, telephone):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO clients (prenom, nom, nom_entreprise, adresse, email, telephone)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (prenom or "", nom or "", nom_entreprise or "", adresse or "", email or "", telephone or ""))
    conn.commit()
    cid = c.lastrowid
    conn.close()
    return cid

def update_client(cid, prenom=None, nom=None, nom_entreprise=None, adresse=None, email=None, telephone=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE clients SET
            prenom = COALESCE(NULLIF(?,''), prenom),
            nom = COALESCE(NULLIF(?,''), nom),
            nom_entreprise = COALESCE(NULLIF(?,''), nom_entreprise),
            adresse = COALESCE(NULLIF(?,''), adresse),
            email = COALESCE(NULLIF(?,''), email),
            telephone = COALESCE(NULLIF(?,''), telephone)
        WHERE id = ?
    """, (prenom, nom, nom_entreprise, adresse, email, telephone, cid))
    conn.commit()
    conn.close()

def find_or_create_client(prenom, nom, entreprise, adresse, email, tel):
    """
    Recherche prioritaire par email/tel si fournis (normalisés),
    sinon par (prenom, nom, entreprise) normalisés.
    Met à jour les infos manquantes si trouvé, sinon insère.
    """
    prenom_n = _norm_text(prenom)
    nom_n    = _norm_text(nom)
    ent_n    = _norm_text(entreprise)
    email_n  = _norm_email(email)
    tel_n    = _norm_phone(tel)

    conn = get_conn()
    c = conn.cursor()

    cid = None
    if email_n:
        c.execute("""
            SELECT id FROM clients
            WHERE lower(trim(coalesce(email,''))) = ?
            LIMIT 1
        """, (email_n,))
        r = c.fetchone()
        if r: cid = r["id"]

    if cid is None and tel_n:
        c.execute("""
            SELECT id FROM clients
            WHERE replace(replace(replace(replace(coalesce(telephone,''),' ',''),'.',''),'-',''),'+','') = ?
            LIMIT 1
        """, (tel_n,))
        r = c.fetchone()
        if r: cid = r["id"]

    if cid is None:
        c.execute("""
            SELECT id FROM clients
            WHERE lower(trim(coalesce(prenom,''))) = ?
              AND lower(trim(coalesce(nom,''))) = ?
              AND lower(trim(coalesce(nom_entreprise,''))) = ?
            LIMIT 1
        """, (prenom_n, nom_n, ent_n))
        r = c.fetchone()
        if r: cid = r["id"]

    if cid is not None:
        c.execute("""
            UPDATE clients SET
                adresse   = COALESCE(NULLIF(?,''), adresse),
                email     = COALESCE(NULLIF(?,''), email),
                telephone = COALESCE(NULLIF(?,''), telephone),
                prenom    = COALESCE(NULLIF(?,''), prenom),
                nom       = COALESCE(NULLIF(?,''), nom),
                nom_entreprise = COALESCE(NULLIF(?,''), nom_entreprise)
            WHERE id = ?
        """, (adresse or "", email or "", tel or "", prenom or "", nom or "", entreprise or "", cid))
        conn.commit()
        conn.close()
        return cid

    # insertion protégée (l'index unique empêchera un vrai doublon)
    try:
        c.execute("""
            INSERT INTO clients (prenom, nom, nom_entreprise, adresse, email, telephone)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (prenom or "", nom or "", entreprise or "", adresse or "", email or "", tel or ""))
        conn.commit()
        cid = c.lastrowid
    except sqlite3.IntegrityError:
        # Récupère l'id de l’enregistrement équivalent
        c.execute("""
            SELECT id FROM clients
            WHERE lower(trim(coalesce(prenom,''))) = ?
              AND lower(trim(coalesce(nom,''))) = ?
              AND lower(trim(coalesce(nom_entreprise,''))) = ?
              AND lower(trim(coalesce(email,''))) = ?
              AND replace(replace(replace(replace(coalesce(telephone,''),' ',''),'.',''),'-',''),'+','') = ?
            LIMIT 1
        """, (prenom_n, nom_n, ent_n, email_n, tel_n))
        r = c.fetchone()
        cid = r["id"] if r else None

    conn.close()
    return cid

def search_clients(term, limit=50):
    conn = get_conn()
    c = conn.cursor()
    like = f"%{(term or '').lower()}%"
    c.execute("""
        SELECT id, prenom, nom, nom_entreprise, adresse, email, telephone
        FROM clients
        WHERE lower(coalesce(prenom,'')) LIKE ?
           OR lower(coalesce(nom,'')) LIKE ?
           OR lower(coalesce(nom_entreprise,'')) LIKE ?
           OR lower(coalesce(email,'')) LIKE ?
           OR replace(replace(replace(replace(coalesce(telephone,''),' ',''),'.',''),'-',''),'+','') LIKE replace(replace(replace(replace(?,' ',''),'.',''),'-',''),'+','')
        ORDER BY nom_entreprise IS NULL, nom, prenom
        LIMIT ?
    """, (like, like, like, like, term or "", limit))
    rows = c.fetchall()
    conn.close()
    return rows

# ---------- Factures ----------
def generate_invoice_number():
    today = datetime.now().strftime("%Y%m%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM invoices WHERE facture_num LIKE ?", (today + "%",))
    seq = (c.fetchone()[0] or 0) + 1
    conn.close()
    return f"{today}-{seq:04d}"

def insert_invoice(client_id, facture_num, date, subtotal, tva, total, notes, items):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO invoices (facture_num, client_id, date, subtotal, tva, total, notes, pdf_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (facture_num, client_id, date, subtotal, tva, total, notes, ""))
    invoice_id = c.lastrowid
    for it in items:
        c.execute("""
            INSERT INTO items (invoice_id, description, qty, price, total)
            VALUES (?, ?, ?, ?, ?)
        """, (invoice_id, it["description"], it["qty"], it["price"], it["total"]))
    conn.commit()
    conn.close()
    return invoice_id

def update_invoice(invoice_id, client_id, date, subtotal, tva, total, notes, items):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE invoices
        SET client_id=?, date=?, subtotal=?, tva=?, total=?, notes=?
        WHERE id=?
    """, (client_id, date, subtotal, tva, total, notes, invoice_id))
    c.execute("DELETE FROM items WHERE invoice_id=?", (invoice_id,))
    for it in items:
        c.execute("""
            INSERT INTO items (invoice_id, description, qty, price, total)
            VALUES (?, ?, ?, ?, ?)
        """, (invoice_id, it["description"], it["qty"], it["price"], it["total"]))
    conn.commit()
    conn.close()

def set_pdf_path(invoice_id, pdf_path):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE invoices SET pdf_path=? WHERE id=?", (pdf_path, invoice_id))
    conn.commit()
    conn.close()

def get_invoice_with_items(invoice_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,))
    inv = c.fetchone()
    c.execute("SELECT * FROM clients WHERE id=?", (inv["client_id"],))
    client = c.fetchone()
    c.execute("SELECT * FROM items WHERE invoice_id=?", (invoice_id,))
    items = c.fetchall()
    conn.close()
    return inv, client, items

def search_invoices(search_term):
    conn = get_conn()
    c = conn.cursor()
    like = "%" + (search_term or "") + "%"
    c.execute("""
        SELECT invoices.*, clients.prenom, clients.nom, clients.nom_entreprise
        FROM invoices
        LEFT JOIN clients ON invoices.client_id = clients.id
        WHERE clients.prenom LIKE ? OR clients.nom LIKE ?
              OR clients.nom_entreprise LIKE ? OR invoices.facture_num LIKE ?
        ORDER BY invoices.date DESC, invoices.id DESC
    """, (like, like, like, like))
    rows = c.fetchall()
    conn.close()
    return rows
