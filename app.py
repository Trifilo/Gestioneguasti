import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "chiave_definitiva_scuola_2026"

# CONFIGURAZIONE DATABASE IN MEMORIA (Niente più errori di file o permessi!)
def get_db_connection():
    # Usiamo un database che vive nella RAM del server
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Creiamo il database globale per questa sessione
db = get_db_connection()

def init_db():
    db.execute("CREATE TABLE utenti (id_utente INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, password TEXT, ruolo TEXT)")
    db.execute("CREATE TABLE segnalazioni (id_segnalazione INTEGER PRIMARY KEY AUTOINCREMENT, titolo TEXT, descrizione TEXT, categoria TEXT, classe TEXT, aula TEXT, stato TEXT DEFAULT 'rosso', data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, id_utente INTEGER)")
    
    # Crea Admin
    pw = generate_password_hash('Admin123!')
    db.execute("INSERT INTO utenti (nome, email, password, ruolo) VALUES ('Admin', 'admin@scuola.it', ?, 'admin')", (pw,))
    db.commit()

# Inizializza subito il DB
init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = db.execute("SELECT * FROM utenti WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session.update({'user_id': user['id_utente'], 'ruolo': user['ruolo'], 'nome': user['nome']})
            return redirect(url_for('index'))
        return render_template('login.html', errore="Email o Password errati.")
    return render_template('login.html')

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/segnalazioni')
def segnalazioni():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('segnalazioni.html')

@app.route('/polling')
def polling():
    if 'user_id' not in session: return jsonify([])
    if session.get('ruolo') == 'admin':
        res = db.execute("SELECT s.*, u.nome as nome_utente FROM segnalazioni s LEFT JOIN utenti u ON s.id_utente = u.id_utente").fetchall()
    else:
        res = db.execute("SELECT s.*, u.nome as nome_utente FROM segnalazioni s LEFT JOIN utenti u ON s.id_utente = u.id_utente WHERE s.id_utente=?", (session['user_id'],)).fetchall()
    return jsonify([dict(row) for row in res])

@app.route('/nuova_segnalazione', methods=['GET', 'POST'])
def nuova_segnalazione():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        db.execute("INSERT INTO segnalazioni (titolo, descrizione, categoria, classe, aula, id_utente) VALUES (?,?,?,?,?,?)",
                  (request.form.get('titolo'), request.form.get('descrizione'), request.form.get('categoria'), request.form.get('classe'), request.form.get('aula'), session['user_id']))
        db.commit()
        return redirect(url_for('segnalazioni'))
    return render_template('nuova_segnalazione.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        pw = generate_password_hash(request.form.get('password'))
        db.execute("INSERT INTO utenti (nome, email, password, ruolo) VALUES (?,?,?,?)", 
                  (request.form.get('nome'), request.form.get('email'), pw, 'studente'))
        db.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/recupera')
def recupera(): return render_template('recupera.html')

@app.route('/cambia_password')
def cambia_password(): return render_template('cambia_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
