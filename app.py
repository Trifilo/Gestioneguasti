from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave_segreta_scuola_2026')
DB_NAME = 'scuola.db'

# ===============================
# FUNZIONI DI SUPPORTO
# ===============================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def valida_password(password):
    # Almeno 8 caratteri, una maiuscola e un numero
    if len(password) < 8:
        return False
    if not re.search("[a-z]", password):
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
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
# DECORATORI
# ===============================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('ruolo') != 'admin': return "Accesso negato", 403
        return f(*args, **kwargs)
    return decorated

# ===============================
# ROTTE
# ===============================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session.update({'user_id': user['id_utente'], 'ruolo': user['ruolo'], 'nome': user['nome']})
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
        except: return "<h3>Email già usata</h3>"
        finally: conn.close()
    return render_template('register.html')

@app.route('/recupera', methods=['GET','POST'])
def recupera():
    if request.method == 'POST':
        email = request.form.get('email')
        nuova_pw = "Reset2026!"
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=?", (email,)).fetchone()
        if user:
            conn.execute("UPDATE utenti SET password=? WHERE email=?", (nuova_pw, email))
            conn.commit()
            conn.close()
            return f"<h3>Password resettata a: {nuova_pw}</h3><a href='/login'>Accedi ora</a>"
        conn.close()
        return "<h3>Email non trovata</h3>"
    return '<h3>Recupero Password</h3><form method="POST"><input type="email" name="email" placeholder="Tua Email" required><button type="submit">Resetta</button></form><br><a href="/login">Torna indietro</a>'

@app.route('/')
@login_required
def index(): return render_template('index.html')

@app.route('/segnalazioni')
@login_required
def segnalazioni():
    conn = get_db_connection()
    if session.get('ruolo') == 'admin':
        # Qui l'Admin vede TUTTO
        res = conn.execute("SELECT s.*, u.nome FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente").fetchall()
    else:
        res = conn.execute("SELECT s.*, u.nome FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente WHERE s.id_utente=?", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('segnalazioni.html', segnalazioni=res)

@app.route('/nuova_segnalazione', methods=['GET','POST'])
@login_required
def nuova_segnalazione():
    if request.method == 'POST':
        dati = (request.form.get('titolo'), request.form.get('descrizione'), request.form.get('categoria'), request.form.get('classe'), request.form.get('aula'), session['user_id'])
        conn = get_db_connection()
        conn.execute("INSERT INTO segnalazioni (titolo,descrizione,categoria,classe,aula,id_utente) VALUES (?,?,?,?,?,?)", dati)
        conn.commit()
        conn.close()
        return redirect(url_for('segnalazioni'))
    return render_template('nuova_segnalazione.html')

@app.route('/aggiorna_stato/<int:id>', methods=['POST'])
@admin_required
def aggiorna_stato(id):
    stato = request.form.get('stato')
    conn = get_db_connection()
    conn.execute("UPDATE segnalazioni SET stato=? WHERE id_segnalazione=?", (stato, id))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)