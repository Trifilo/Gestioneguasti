from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
from functools import wraps
import random, string
import os  # Fondamentale per Render

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_chiave_segretissima_di_default')
DB_NAME = 'scuola.db'

# ===============================
# DATABASE
# ===============================
def get_db_connection():
    # Su Render, il percorso deve essere affidabile
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Tabella utenti
    c.execute("""
    CREATE TABLE IF NOT EXISTS utenti (
        id_utente INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        ruolo TEXT DEFAULT 'studente'
    )
    """)

    # Tabella segnalazioni
    c.execute("""
    CREATE TABLE IF NOT EXISTS segnalazioni (
        id_segnalazione INTEGER PRIMARY KEY AUTOINCREMENT,
        titolo TEXT NOT NULL,
        descrizione TEXT NOT NULL,
        categoria TEXT NOT NULL,
        classe TEXT,
        aula TEXT,
        stato TEXT DEFAULT 'rosso',
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        id_utente INTEGER,
        FOREIGN KEY (id_utente) REFERENCES utenti(id_utente)
    )
    """)

    # Inserimento admin fisso
    c.execute("SELECT * FROM utenti WHERE ruolo='admin'")
    if not c.fetchone():
        c.execute("""
        INSERT INTO utenti (nome,email,password,ruolo)
        VALUES (?,?,?,?)
        """, ('Amministratore','admin@scuola.it','admin123','admin'))

    conn.commit()
    conn.close()

# Inizializza il DB all'avvio
init_db()

# ===============================
# DECORATORI
# ===============================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('ruolo') != 'admin':
            return "Accesso negato", 403
        return f(*args, **kwargs)
    return decorated

# ===============================
# GENERA PASSWORD PROVVISORIA
# ===============================
def genera_password():
    caratteri = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pw = ''.join(random.choice(caratteri) for _ in range(8))
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw) and any(c in "!@#$%^&*" for c in pw)):
            return pw

# ===============================
# ROTTE (LOGIN, LOGOUT, REGISTER)
# ===============================
@app.route('/login', methods=['GET','POST'])
def login():
    errore = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=? AND password=?", (email,password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id_utente']
            session['ruolo'] = user['ruolo']
            session['nome'] = user['nome']
            return redirect(url_for('index'))
        errore = "Credenziali errate"
    return render_template('login.html', errore=errore)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    errore = None
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')

        if len(password) < 8 or not any(c.isupper() for c in password) \
           or not any(c.islower() for c in password) or not any(c.isdigit() for c in password) \
           or not any(c in "!@#$%^&*" for c in password):
            errore = "Password non valida: minimo 8 caratteri, maiuscole/minuscole, numeri e simboli"
            return render_template('register.html', errore=errore)

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)",
                         (nome,email,password,'studente'))
            conn.commit()
        except sqlite3.IntegrityError:
            errore = "Email già registrata"
            return render_template('register.html', errore=errore)
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html', errore=errore)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# ... (tutte le altre tue rotte rimangono uguali) ...
@app.route('/segnalazioni')
@login_required
def segnalazioni():
    conn = get_db_connection()
    if session.get('ruolo') == 'admin':
        segnalazioni = conn.execute("SELECT s.*, u.nome AS nome_utente FROM segnalazioni s LEFT JOIN utenti u ON s.id_utente=u.id_utente ORDER BY s.data DESC").fetchall()
    else:
        segnalazioni = conn.execute("SELECT s.*, u.nome AS nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente=u.id_utente WHERE s.id_utente=? ORDER BY s.data DESC",(session['user_id'],)).fetchall()
    conn.close()
    return render_template('segnalazioni.html', segnalazioni=segnalazioni)

# ===============================
# AVVIO (CORRETTO PER RENDER)
# ===============================
if __name__ == '__main__':
    # Render imposta automaticamente una variabile d'ambiente chiamata PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
