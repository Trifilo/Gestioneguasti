from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
from functools import wraps
import random, string
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave_segreta_scuola_2026')
DB_NAME = 'scuola.db'

# ===============================
# DATABASE
# ===============================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS utenti (
        id_utente INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        ruolo TEXT DEFAULT 'studente'
    )
    """)
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
    c.execute("SELECT * FROM utenti WHERE ruolo='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", 
                 ('Amministratore','admin@scuola.it','admin123','admin'))
    conn.commit()
    conn.close()

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
# ROTTE AUTENTICAZIONE
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
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)",
                         (nome,email,password,'studente'))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            errore = "Email già registrata"
        finally:
            conn.close()
    return render_template('register.html', errore=errore)

# ===============================
# ROTTE SEGNALAZIONI
# ===============================
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/segnalazioni')
@login_required
def segnalazioni():
    conn = get_db_connection()
    if session.get('ruolo') == 'admin':
        res = conn.execute("SELECT s.*, u.nome AS nome_utente FROM segnalazioni s LEFT JOIN utenti u ON s.id_utente=u.id_utente ORDER BY s.data DESC").fetchall()
    else:
        res = conn.execute("SELECT s.*, u.nome AS nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente=u.id_utente WHERE s.id_utente=? ORDER BY s.data DESC",(session['user_id'],)).fetchall()
    conn.close()
    return render_template('segnalazioni.html', segnalazioni=res)

@app.route('/nuova_segnalazione', methods=['GET','POST'])
@login_required
def nuova_segnalazione():
    if session.get('ruolo') == 'admin':
        return "Gli admin non possono inserire segnalazioni", 403
    if request.method == 'POST':
        titolo = request.form.get('titolo')
        descrizione = request.form.get('descrizione')
        categoria = request.form.get('categoria')
        classe = request.form.get('classe')
        aula = request.form.get('aula')
        conn = get_db_connection()
        conn.execute("INSERT INTO segnalazioni (titolo,descrizione,categoria,classe,aula,id_utente) VALUES (?,?,?,?,?,?)",
                     (titolo, descrizione, categoria, classe, aula, session['user_id']))
        conn.commit()
        conn.close()
        return redirect(url_for('segnalazioni'))
    return render_template('nuova_segnalazione.html')

# ===============================
# AZIONI ADMIN
# ===============================
@app.route('/aggiorna_stato/<int:id_segnalazione>', methods=['POST'])
@admin_required
def aggiorna_stato(id_segnalazione):
    stato = request.form.get('stato')
    conn = get_db_connection()
    conn.execute("UPDATE segnalazioni SET stato=? WHERE id_segnalazione=?",(stato,id_segnalazione))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id_segnalazione>', methods=['POST'])
@admin_required
def elimina_segnalazione(id_segnalazione):
    conn = get_db_connection()
    conn.execute("DELETE FROM segnalazioni WHERE id_segnalazione=?",(id_segnalazione,))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

# ===============================
# ROTTE "SALVA-SITO" (Evitano i BuildError)
# ===============================
@app.route('/recupera')
def recupera():
    return "Funzione di recupero password in fase di manutenzione. Contatta l'amministratore."

@app.route('/profilo')
@login_required
def profilo():
    return f"Profilo di {session.get('nome')} - Funzione in arrivo."

# ===============================
# AVVIO PER RENDER
# ===============================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)