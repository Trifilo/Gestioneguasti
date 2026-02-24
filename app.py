from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
from functools import wraps
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
    # Verifica admin di default
    c.execute("SELECT * FROM utenti WHERE ruolo='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", 
                 ('Amministratore','admin@scuola.it','admin123','admin'))
    conn.commit()
    conn.close()

init_db()

# ===============================
# PROTEZIONE ACCESSI
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
        # Controllo ruolo ignorando maiuscole/minuscole
        ruolo = str(session.get('ruolo', '')).lower()
        if ruolo != 'admin':
            return "Accesso negato: area riservata agli amministratori", 403
        return f(*args, **kwargs)
    return decorated

# ===============================
# AUTENTICAZIONE
# ===============================
@app.route('/login', methods=['GET','POST'])
def login():
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
        return "<h3>Credenziali errate.</h3><br><a href='/login'>Riprova</a>"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
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
            return "<h3>Email già registrata.</h3><br><a href='/register'>Riprova</a>"
        finally:
            conn.close()
    return render_template('register.html')

# ===============================
# SEGNALAZIONI (LATO UTENTE E ADMIN)
# ===============================
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/segnalazioni')
@login_required
def segnalazioni():
    conn = get_db_connection()
    ruolo_corrente = str(session.get('ruolo', '')).lower()
    
    if ruolo_corrente == 'admin':
        # ADMIN: vede tutto con i nomi degli utenti
        res = conn.execute("""
            SELECT s.*, u.nome AS nome_utente 
            FROM segnalazioni s 
            LEFT JOIN utenti u ON s.id_utente = u.id_utente 
            ORDER BY s.data DESC
        """).fetchall()
    else:
        # UTENTE: vede solo le proprie
        res = conn.execute("""
            SELECT s.*, u.nome AS nome_utente 
            FROM segnalazioni s 
            JOIN utenti u ON s.id_utente = u.id_utente 
            WHERE s.id_utente = ? 
            ORDER BY s.data DESC
        """, (session['user_id'],)).fetchall()
    conn.close()
    return render_template('segnalazioni.html', segnalazioni=res)

@app.route('/nuova_segnalazione', methods=['GET','POST'])
@login_required
def nuova_segnalazione():
    if str(session.get('ruolo', '')).lower() == 'admin':
        return "Gli amministratori non possono inserire segnalazioni.", 403
        
    if request.method == 'POST':
        # Recupero dati con valori di backup per evitare crash
        titolo = request.form.get('titolo', 'Senza Titolo')
        descrizione = request.form.get('descrizione', 'Nessuna descrizione')
        categoria = request.form.get('categoria', 'Altro')
        classe = request.form.get('classe', '-')
        aula = request.form.get('aula', '-')
        user_id = session.get('user_id')

        try:
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO segnalazioni (titolo, descrizione, categoria, classe, aula, id_utente, stato) 
                VALUES (?, ?, ?, ?, ?, ?, 'rosso')
            """, (titolo, descrizione, categoria, classe, aula, user_id))
            conn.commit()
            conn.close()
            return redirect(url_for('segnalazioni'))
        except Exception as e:
            return f"Errore durante l'invio: {str(e)}"
            
    return render_template('nuova_segnalazione.html')

# ===============================
# AZIONI ADMIN (STATO ED ELIMINAZIONE)
# ===============================
@app.route('/aggiorna_stato/<int:id_segnalazione>', methods=['POST'])
@admin_required
def aggiorna_stato(id_segnalazione):
    nuovo_stato = request.form.get('stato')
    if nuovo_stato in ['rosso', 'giallo', 'verde']:
        conn = get_db_connection()
        conn.execute("UPDATE segnalazioni SET stato=? WHERE id_segnalazione=?", (nuovo_stato, id_segnalazione))
        conn.commit()
        conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id_segnalazione>', methods=['POST'])
@admin_required
def elimina_segnalazione(id_segnalazione):
    conn = get_db_connection()
    conn.execute("DELETE FROM segnalazioni WHERE id_segnalazione=?", (id_segnalazione,))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

# ===============================
# ALTRE UTILITIES
# ===============================
@app.route('/recupera', methods=['GET', 'POST'])
def recupera():
    if request.method == 'POST':
        email = request.form.get('email')
        nuova_pw = "Scuola2026!"
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=?", (email,)).fetchone()
        if user:
            conn.execute("UPDATE utenti SET password=? WHERE email=?", (nuova_pw, email))
            conn.commit()
            conn.close()
            return f"Password resettata a: <b>{nuova_pw}</b>. <a href='/login'>Accedi</a>"
        conn.close()
        return "Email non trovata. <a href='/recupera'>Riprova</a>"
    return '<h3>Recupero Password</h3><form method="POST"><input type="email" name="email" required><button type="submit">Resetta</button></form>'

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)