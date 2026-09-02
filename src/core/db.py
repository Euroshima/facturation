# core/db.py
import re
import psycopg2
import psycopg2.extras
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from .dbconfig import database_url

# ---------- Connexion ----------
# Les identifiants ne sont plus dans le code : voir core/dbconfig.py
# (fichier de config écrit par l'app, ou variables d'environnement DB_*).

def get_conn():
    """Ouvre une connexion. Relit la config à chaque appel : une modification
    dans les paramètres est prise en compte sans redémarrer."""
    return psycopg2.connect(database_url())


def try_connect(url: str):
    """Teste une URL de connexion. Retourne (True, "") ou (False, message)."""
    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        conn.close()
        return True, ""
    except Exception as e:
        return False, str(e).strip()

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

# ---------- Déduplication ----------
def _dedupe_clients_core(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
          WITH norm AS (
            SELECT
              id,
              lower(trim(coalesce(prenom,''))) AS p,
              lower(trim(coalesce(nom,''))) AS n,
              lower(trim(coalesce(nom_entreprise,''))) AS e,
              lower(trim(coalesce(email,''))) AS mail,
              regexp_replace(coalesce(telephone,''), E'\\D+', '', 'g') AS tel
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
            cur.execute("UPDATE invoices SET client_id=%s WHERE client_id=%s", (keep_id, dup_id))
            cur.execute("DELETE FROM clients WHERE id=%s", (dup_id,))
        conn.commit()

def dedupe_clients():
    conn = get_conn()
    try:
        _dedupe_clients_core(conn)
    finally:
        conn.close()

# ---------- Schéma / Index ----------
def init_db():
    conn = get_conn()
    with conn.cursor() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS clients(
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
                facture_num TEXT UNIQUE,
                client_id INTEGER REFERENCES clients(id),
                date TEXT,
                subtotal REAL,
                tva REAL,
                total REAL,
                pdf_path TEXT,
                notes TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS items(
                id SERIAL PRIMARY KEY,
                invoice_id INTEGER REFERENCES invoices(id),
                description TEXT,
                qty REAL,
                unit VARCHAR(10) DEFAULT 'kg',
                price REAL,
                total REAL
            )
        """)
        conn.commit()

    _dedupe_clients_core(conn)

    with conn.cursor() as c:
        try:
            c.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_identity
                ON clients(
                  lower(trim(coalesce(prenom,''))),
                  lower(trim(coalesce(nom,''))),
                  lower(trim(coalesce(nom_entreprise,''))),
                  lower(trim(coalesce(email,''))),
                  regexp_replace(coalesce(telephone,''), E'\\D+', '', 'g')
                )
            """)
            conn.commit()
        except psycopg2.IntegrityError:
            _dedupe_clients_core(conn)
            c.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_identity
                ON clients(
                  lower(trim(coalesce(prenom,''))),
                  lower(trim(coalesce(nom,''))),
                  lower(trim(coalesce(nom_entreprise,''))),
                  lower(trim(coalesce(email,''))),
                  regexp_replace(coalesce(telephone,''), E'\\D+', '', 'g')
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
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO clients (prenom, nom, nom_entreprise, adresse, email, telephone)
                VALUES (%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (prenom or "", nom or "", nom_entreprise or "", adresse or "", email or "", telephone or ""))
            cid = c.fetchone()[0]
            conn.commit()
            return cid
    finally:
        conn.close()

def update_client(cid, prenom=None, nom=None, nom_entreprise=None, adresse=None, email=None, telephone=None):
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("""
                UPDATE clients SET
                    prenom = COALESCE(NULLIF(%s,''), prenom),
                    nom = COALESCE(NULLIF(%s,''), nom),
                    nom_entreprise = COALESCE(NULLIF(%s,''), nom_entreprise),
                    adresse = COALESCE(NULLIF(%s,''), adresse),
                    email = COALESCE(NULLIF(%s,''), email),
                    telephone = COALESCE(NULLIF(%s,''), telephone)
                WHERE id=%s
            """, (prenom, nom, nom_entreprise, adresse, email, telephone, cid))
            conn.commit()
    finally:
        conn.close()

def find_or_create_client(prenom, nom, entreprise, adresse, email, tel):
    prenom_n = _norm_text(prenom)
    nom_n = _norm_text(nom)
    ent_n = _norm_text(entreprise)
    email_n = _norm_email(email)
    tel_n = _norm_phone(tel)

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as c:
            cid = None
            if email_n:
                c.execute("""
                    SELECT id FROM clients
                    WHERE lower(trim(coalesce(email,''))) = %s
                    LIMIT 1
                """, (email_n,))
                r = c.fetchone()
                if r: cid = r["id"]

            if cid is None and tel_n:
                c.execute("""
                    SELECT id FROM clients
                    WHERE regexp_replace(coalesce(telephone,''), E'\\D+', '', 'g') = %s
                    LIMIT 1
                """, (tel_n,))
                r = c.fetchone()
                if r: cid = r["id"]

            if cid is None:
                c.execute("""
                    SELECT id FROM clients
                    WHERE lower(trim(coalesce(prenom,''))) = %s
                      AND lower(trim(coalesce(nom,''))) = %s
                      AND lower(trim(coalesce(nom_entreprise,''))) = %s
                    LIMIT 1
                """, (prenom_n, nom_n, ent_n))
                r = c.fetchone()
                if r: cid = r["id"]

            if cid is not None:
                c.execute("""
                    UPDATE clients SET
                        adresse = COALESCE(NULLIF(%s,''), adresse),
                        email = COALESCE(NULLIF(%s,''), email),
                        telephone = COALESCE(NULLIF(%s,''), telephone),
                        prenom = COALESCE(NULLIF(%s,''), prenom),
                        nom = COALESCE(NULLIF(%s,''), nom),
                        nom_entreprise = COALESCE(NULLIF(%s,''), nom_entreprise)
                    WHERE id=%s
                """, (adresse or "", email or "", tel or "", prenom or "", nom or "", entreprise or "", cid))
                conn.commit()
                return cid

            c.execute("""
                INSERT INTO clients (prenom, nom, nom_entreprise, adresse, email, telephone)
                VALUES (%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (prenom or "", nom or "", entreprise or "", adresse or "", email or "", tel or ""))
            cid = c.fetchone()[0]
            conn.commit()
            return cid
    finally:
        conn.close()

def search_clients(term, limit=50):
    like = f"%{(term or '').lower()}%"
    # Recherche téléphone : on compare les chiffres seuls, avec jokers.
    tel_digits = re.sub(r"\D+", "", term or "")
    tel_like = f"%{tel_digits}%" if tel_digits else like
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as c:
            c.execute("""
                SELECT id, prenom, nom, nom_entreprise, adresse, email, telephone
                FROM clients
                WHERE lower(coalesce(prenom,'')) LIKE %s
                   OR lower(coalesce(nom,'')) LIKE %s
                   OR lower(coalesce(nom_entreprise,'')) LIKE %s
                   OR lower(coalesce(email,'')) LIKE %s
                   OR regexp_replace(coalesce(telephone,''), E'\\D+', '', 'g') LIKE %s
                ORDER BY nom_entreprise IS NULL, nom, prenom
                LIMIT %s
            """, (like, like, like, like, tel_like, limit))
            return c.fetchall()
    finally:
        conn.close()

# ---------- Factures ----------
def generate_invoice_number():
    today = datetime.now().strftime("%Y%m%d")
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM invoices WHERE facture_num LIKE %s", (today + "%",))
            seq = (c.fetchone()[0] or 0) + 1
            return f"{today}-{seq:04d}"
    finally:
        conn.close()

def insert_invoice(client_id, facture_num, date, subtotal, tva, total, notes, items):
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO invoices (facture_num, client_id, date, subtotal, tva, total, notes, pdf_path)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'')
                RETURNING id
            """, (facture_num, client_id, date, subtotal, tva, total, notes))
            invoice_id = c.fetchone()[0]
            for it in items:
                c.execute("""
                    INSERT INTO items (invoice_id, description, qty, unit, price, total)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (invoice_id, it["description"], it["qty"], it.get("unit","kg"), it["price"], it["total"]))
            conn.commit()
            return invoice_id
    finally:
        conn.close()

def update_invoice(invoice_id, client_id=None, date=None, subtotal=None, tva=None, total=None, notes=None, items=None):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as c:
            # Vérifie que la facture existe
            c.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
            invoice = c.fetchone()
            if not invoice:
                raise ValueError(f"Facture {invoice_id} introuvable.")

            # Met à jour seulement les champs fournis
            new_client_id = client_id or invoice["client_id"]
            new_date = date or invoice["date"]
            new_subtotal = subtotal if subtotal is not None else invoice["subtotal"]
            new_tva = tva if tva is not None else invoice["tva"]
            new_total = total if total is not None else invoice["total"]
            new_notes = notes if notes is not None else invoice["notes"]

            c.execute("""
                UPDATE invoices
                SET client_id=%s, date=%s, subtotal=%s, tva=%s, total=%s, notes=%s
                WHERE id=%s
            """, (new_client_id, new_date, new_subtotal, new_tva, new_total, new_notes, invoice_id))

            # Met à jour les items si fournis
            if items is not None:
                # Supprime les anciens
                c.execute("DELETE FROM items WHERE invoice_id=%s", (invoice_id,))
                for it in items:
                    c.execute("""
                        INSERT INTO items (invoice_id, description, qty, unit, price, total)
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """, (
                        invoice_id,
                        it["description"],
                        it["qty"],
                        it.get("unit", "kg"),
                        it["price"],
                        it["total"]
                    ))
            conn.commit()
            return invoice_id
    finally:
        conn.close()

def set_pdf_path(invoice_id, pdf_path):
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("UPDATE invoices SET pdf_path=%s WHERE id=%s", (pdf_path, invoice_id))
            conn.commit()
    finally:
        conn.close()

def get_invoice_with_items(invoice_id):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as c:
            c.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
            inv = c.fetchone()
            if not inv:
                print(f"Aucune facture trouvée pour id={invoice_id}")
                return None, None, []

            c.execute("SELECT * FROM clients WHERE id=%s", (inv["client_id"],))
            client = c.fetchone()

            c.execute("SELECT * FROM items WHERE invoice_id=%s", (invoice_id,))
            items = c.fetchall()

            return inv, client, items
    finally:
        conn.close()


def search_invoices(search_term):
    term = (search_term or "").strip()
    like = f"%{term}%"
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as c:
            # ILIKE = insensible à la casse. Le terme vide renvoie toutes les
            # factures (y compris celles sans client, filtrables par numéro).
            c.execute("""
                SELECT invoices.*, clients.prenom, clients.nom, clients.nom_entreprise
                FROM invoices
                LEFT JOIN clients ON invoices.client_id = clients.id
                WHERE %s = ''
                   OR coalesce(clients.prenom,'') ILIKE %s
                   OR coalesce(clients.nom,'') ILIKE %s
                   OR coalesce(clients.nom_entreprise,'') ILIKE %s
                   OR coalesce(invoices.facture_num,'') ILIKE %s
                ORDER BY invoices.date DESC, invoices.id DESC
            """, (term, like, like, like, like))
            return c.fetchall()
    finally:
        conn.close()