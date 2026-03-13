import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
# Usiamo una chiave fissa per evitare di essere buttati fuori a ogni riavvio
app.secret_key = "chiave_segreta_scuola_2026"

# SOLUZIONE RENDER: Usiamo la cartella /tmp per il database
DB_PATH = "/tmp/scuola.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea le tabelle e l'admin se il database non esiste."""
    conn = get_db_connection()
    # Tabella Utenti
    conn.execute("""CREATE TABLE IF NOT EXISTS utenti (
        id_utente INTEGER PRIMARY KEY AUTOINCREMENT, 
        nome TEXT, 
        email TEXT UNIQUE, 
        password TEXT, 
        ruolo TEXT DEFAULT 'studente')""")
    
    # Tabella Segnalazioni
    conn.execute("""CREATE TABLE IF NOT EXISTS segnalazioni (
        id_segnalazione INTEGER PRIMARY KEY AUTOINCREMENT, 
        titolo TEXT, 
        descrizione TEXT, 
        categoria TEXT, 
        classe TEXT, 
        aula TEXT, 
        stato TEXT DEFAULT 'rosso', 
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        id_utente INTEGER)""")
    
    # CREAZIONE/RESET ADMIN (Sempre attivo)
    hashed_pw = generate_password_hash('Admin123!')
    conn.execute("DELETE FROM utenti WHERE email='admin@scuola.it'")
    conn.execute("INSERT INTO utenti (nome, email, password, ruolo) VALUES (?,?,?,?)", 
                ('Admin', 'admin@scuola.it', hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()

# Inizializza il DB all'avvio
if not os.path.exists(DB_PATH) or True: # Il True forza il check dell'admin
    init_db()

# Decoratore per proteggere le pagine
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTTE ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id_utente']
            session['ruolo'] = user['ruolo']
            session['nome'] = user['nome']
            return redirect(url_for('index'))
        
        return render_template('login.html', errore="Credenziali non valide.")
    return render_template('login.html')

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
    try:
        # Se admin vede tutto, se utente vede solo le sue
        if session.get('ruolo') == 'admin':
            res = conn.execute("""
                SELECT s.*, u.nome as nome_utente 
                FROM segnalazioni s 
                LEFT JOIN utenti u ON s.id_utente = u.id_utente 
                ORDER BY s.data DESC""").fetchall()
        else:
            res = conn.execute("""
                SELECT s.*, u.nome as nome_utente 
                FROM segnalazioni s 
                LEFT JOIN utenti u ON s.id_utente = u.id_utente 
                WHERE s.id_utente = ? 
                ORDER BY s.data DESC""", (session['user_id'],)).fetchall()
        
        return jsonify([dict(row) for row in res])
    except Exception as e:
        return jsonify({"errore": str(e)}), 500
    finally:
        conn.close()

@app.route('/nuova_segnalazione', methods=['GET', 'POST'])
@login_required
def nuova_segnalazione():
    if request.method == 'POST':
        titolo = request.form.get('titolo')
        descrizione = request.form.get('descrizione')
        categoria = request.form.get('categoria')
        classe = request.form.get('classe')
        aula = request.form.get('aula')
        
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO segnalazioni (titolo, descrizione, categoria, classe, aula, id_utente) 
            VALUES (?, ?, ?, ?, ?, ?)""", 
            (titolo, descrizione, categoria, classe, aula, session['user_id']))
        conn.commit()
        conn.close()
        return redirect(url_for('segnalazioni'))
    
    return render_template('nuova_segnalazione.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Avvio (per locale, su Render usa Gunicorn)
if __name__ == '__main__':
    app.run(debug=True)
