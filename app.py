from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from functools import wraps
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave_segreta_scuola_2026')
DB_NAME = 'scuola.db'

# ===============================
# DATABASE E SICUREZZA
# ===============================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def valida_password(password):
    """Almeno 8 caratteri, una maiuscola e un numero."""
    if len(password) < 8 or not re.search("[A-Z]", password) or not re.search("[0-9]", password):
        return False
    return True

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS utenti (id_utente INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, password TEXT, ruolo TEXT DEFAULT 'studente')")
    c.execute("CREATE TABLE IF NOT EXISTS segnalazioni (id_segnalazione INTEGER PRIMARY KEY AUTOINCREMENT, titolo TEXT, descrizione TEXT, categoria TEXT, classe TEXT, aula TEXT, stato TEXT DEFAULT 'rosso', data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, id_utente INTEGER, FOREIGN KEY (id_utente) REFERENCES utenti(id_utente))")
    c.execute("SELECT * FROM utenti WHERE email='admin@scuola.it'")
    if not c.fetchone():
        c.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", ('Admin','admin@scuola.it','Admin123!','admin'))
    conn.commit()
    conn.close()

init_db()

# ===============================
# PROTEZIONE
# ===============================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ===============================
# AUTENTICAZIONE
# ===============================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session.update({'user_id': user['id_utente'], 'ruolo': str(user['ruolo']).lower(), 'nome': user['nome']})
            return redirect(url_for('index'))
        return "<h3>Credenziali errate</h3><a href='/login'>Riprova</a>"
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nome, email, password = request.form.get('nome'), request.form.get('email'), request.form.get('password')
        if not valida_password(password):
            return "<h3>La password deve avere 8 caratteri, una maiuscola e un numero.</h3><a href='/register'>Riprova</a>"
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", (nome,email,password,'studente'))
            conn.commit()
            return redirect(url_for('login'))
        except: return "<h3>Email già in uso</h3><a href='/register'>Riprova</a>"
        finally: conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ===============================
# RECUPERO PASSWORD
# ===============================
@app.route('/recupera', methods=['GET', 'POST'])
def recupera():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=?", (email,)).fetchone()
        if user:
            conn.execute("UPDATE utenti SET password='Reset2026!' WHERE email=?", (email,))
            conn.commit()
            conn.close()
            return "<h3>Password resettata a: Reset2026!</h3><a href='/login'>Accedi</a>"
        conn.close()
        return "<h3>Email non trovata</h3>"
    return '<h3>Recupero</h3><form method="POST"><input name="email" type="email" required><button>Invia</button></form>'

# ===============================
# SEGNALAZIONI (FIX INVIO E ADMIN)
# ===============================
@app.route('/')
@login_required
def index(): return render_template('index.html')

@app.route('/segnalazioni')
@login_required
def segnalazioni():
    conn = get_db_connection()
    # L'admin vede tutto, l'utente solo le sue
    if session.get('ruolo') == 'admin':
        res = conn.execute("SELECT s.*, u.nome FROM segnalazioni s LEFT JOIN utenti u ON s.id_utente = u.id_utente ORDER BY s.data DESC").fetchall()
    else:
        res = conn.execute("SELECT s.*, u.nome FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente WHERE s.id_utente=? ORDER BY s.data DESC", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('segnalazioni.html', segnalazioni=res)

@app.route('/nuova_segnalazione', methods=['GET','POST'])
@login_required
def nuova_segnalazione():
    if request.method == 'POST':
        # Recupero "tollerante": prova più nomi per ogni campo
        t = request.form.get('titolo') or request.form.get('oggetto') or "Segnalazione"
        d = request.form.get('descrizione') or request.form.get('messaggio') or "-"
        c = request.form.get('categoria') or "Altro"
        cl = request.form.get('classe') or "-"
        au = request.form.get('aula') or "-"
        uid = session.get('user_id')

        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO segnalazioni (titolo, descrizione, categoria, classe, aula, id_utente, stato) VALUES (?,?,?,?,?,?, 'rosso')", (t, d, c, cl, au, uid))
            conn.commit()
            conn.close()
            return redirect(url_for('segnalazioni'))
        except Exception as e:
            return f"Errore nell'invio: {e}"
    return render_template('nuova_segnalazione.html')

@app.route('/aggiorna_stato/<int:id>', methods=['POST'])
def aggiorna_stato(id):
    if session.get('ruolo') != 'admin': return "Non autorizzato", 403
    nuovo_stato = request.form.get('stato')
    conn = get_db_connection()
    conn.execute("UPDATE segnalazioni SET stato=? WHERE id_segnalazione=?", (nuovo_stato, id))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id>', methods=['POST'])
def elimina_segnalazione(id):
    if session.get('ruolo') != 'admin': return "Non autorizzato", 403
    conn = get_db_connection()
    conn.execute("DELETE FROM segnalazioni WHERE id_segnalazione=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)