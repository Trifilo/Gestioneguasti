from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
import re
import string
import random
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave_segreta_scuola_2026')

# Percorso assoluto per il database SQLite
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'scuola.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Questo permette di accedere alle colonne per nome
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Tabella Utenti
    cur.execute("""CREATE TABLE IF NOT EXISTS utenti (
        id_utente INTEGER PRIMARY KEY AUTOINCREMENT, 
        nome TEXT, 
        email TEXT UNIQUE, 
        password TEXT, 
        ruolo TEXT DEFAULT 'studente')""")
    
    # Tabella Segnalazioni
    cur.execute("""CREATE TABLE IF NOT EXISTS segnalazioni (
        id_segnalazione INTEGER PRIMARY KEY AUTOINCREMENT, 
        titolo TEXT, 
        descrizione TEXT, 
        categoria TEXT, 
        classe TEXT, 
        aula TEXT, 
        stato TEXT DEFAULT 'rosso', 
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        id_utente INTEGER,
        FOREIGN KEY (id_utente) REFERENCES utenti(id_utente))""")
    
    # Admin predefinito
    cur.execute("SELECT * FROM utenti WHERE email='admin@scuola.it'")
    if not cur.fetchone():
        hashed_pw = generate_password_hash('Admin123!')
        cur.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", 
                   ('Admin','admin@scuola.it', hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()

# Inizializza il DB all'avvio
init_db()

# --- DECORATORI ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# --- ROTTE AUTH ---
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=?", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session.update({'user_id': user['id_utente'], 'ruolo': user['ruolo'], 'nome': user['nome']})
            return redirect(url_for('index'))
        return render_template('login.html', errore="Credenziali non valide.")
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if len(password) < 8:
            return render_template('register.html', errore="Password troppo corta.")
        
        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", 
                        (nome, email, hashed_pw, 'studente'))
            conn.commit()
            return redirect(url_for('login'))
        except:
            return render_template('register.html', errore="Email già esistente.")
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/recupera', methods=['GET','POST'])
def recupera():
    if request.method == 'POST':
        email = request.form.get('email')
        nuova_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        hashed_pw = generate_password_hash(nuova_pass)
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=?", (email,)).fetchone()
        if user:
            conn.execute("UPDATE utenti SET password=? WHERE email=?", (hashed_pw, email))
            conn.commit()
            conn.close()
            return render_template('recupera.html', msg=f"Nuova password temporanea: {nuova_pass}")
        conn.close()
        return render_template('recupera.html', errore="Email non trovata.")
    return render_template('recupera.html')

@app.route('/cambia_password', methods=['GET','POST'])
@login_required
def cambia_password():
    if request.method == 'POST':
        nuova_pw = request.form.get('nuova_password')
        if len(nuova_pw) < 8 or not re.search("[A-Z]", nuova_pw):
            return render_template('cambia_password.html', errore="Password non valida.")
        
        hashed_pw = generate_password_hash(nuova_pw)
        conn = get_db_connection()
        conn.execute("UPDATE utenti SET password=? WHERE id_utente=?", (hashed_pw, session['user_id']))
        conn.commit()
        conn.close()
        return render_template('cambia_password.html', msg="Password aggiornata con successo!")
    return render_template('cambia_password.html')

# --- ROTTE CORE ---
@app.route('/')
@login_required
def index(): 
    return render_template('index.html')

@app.route('/segnalazioni')
@login_required
def segnalazioni():
    return render_template('segnalazioni.html')

@app.route('/polling')
@login_required
def polling():
    conn = get_db_connection()
    if session.get('ruolo') == 'admin':
        query = "SELECT s.*, u.nome as nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente ORDER BY s.data DESC"
        res = conn.execute(query).fetchall()
    else:
        query = "SELECT s.*, u.nome as nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente WHERE s.id_utente=? ORDER BY s.data DESC"
        res = conn.execute(query, (session['user_id'],)).fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in res])

@app.route('/nuova_segnalazione', methods=['GET','POST'])
@login_required
def nuova_segnalazione():
    if request.method == 'POST':
        dati = (request.form.get('titolo'), request.form.get('descrizione'), 
                request.form.get('categoria'), request.form.get('classe'), 
                request.form.get('aula'), session['user_id'])
        conn = get_db_connection()
        conn.execute("INSERT INTO segnalazioni (titolo,descrizione,categoria,classe,aula,id_utente) VALUES (?,?,?,?,?,?)", dati)
        conn.commit()
        conn.close()
        return redirect(url_for('segnalazioni'))
    return render_template('nuova_segnalazione.html')

@app.route('/aggiorna_stato/<int:id>', methods=['POST'])
@login_required
def aggiorna_stato(id):
    if session.get('ruolo') != 'admin': return "Accesso negato", 403
    nuovo_stato = request.form.get('stato')
    conn = get_db_connection()
    conn.execute("UPDATE segnalazioni SET stato=? WHERE id_segnalazione=?", (nuovo_stato, id))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id>', methods=['POST'])
@login_required
def elimina_segnalazione(id):
    if session.get('ruolo') != 'admin': return "Accesso negato", 403
    conn = get_db_connection()
    conn.execute("DELETE FROM segnalazioni WHERE id_segnalazione=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run()
