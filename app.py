import os
import sqlite3
import random
import string
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "chiave_definitiva_scuola_2026"

# CONFIGURAZIONE DATABASE IN MEMORIA
def get_db_connection():
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
        email = request.form.get('email')
        # Controllo se l'utente esiste già
        esistente = db.execute("SELECT * FROM utenti WHERE email = ?", (email,)).fetchone()
        if esistente:
            return render_template('register.html', errore="Email già registrata.")
            
        pw = generate_password_hash(request.form.get('password'))
        db.execute("INSERT INTO utenti (nome, email, password, ruolo) VALUES (?,?,?,?)", 
                  (request.form.get('nome'), email, pw, 'studente'))
        db.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/recupera', methods=['GET', 'POST'])
def recupera(): 
    if request.method == 'POST':
        email = request.form.get('email')
        user = db.execute("SELECT * FROM utenti WHERE email = ?", (email,)).fetchone()
        if user:
            # Genera una password temporanea casuale
            temp_pw = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            hashed_pw = generate_password_hash(temp_pw)
            db.execute("UPDATE utenti SET password = ? WHERE email = ?", (hashed_pw, email))
            db.commit()
            return render_template('recupera.html', msg=temp_pw)
        return render_template('recupera.html', errore="Email non trovata nel sistema.")
    return render_template('recupera.html')

@app.route('/cambia_password', methods=['GET', 'POST'])
def cambia_password(): 
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        nuova_password = request.form.get('nuova_password')
        if len(nuova_password) < 8:
            return render_template('cambia_password.html', errore="La password deve avere almeno 8 caratteri.")
            
        hashed_pw = generate_password_hash(nuova_password)
        db.execute("UPDATE utenti SET password = ? WHERE id_utente = ?", (hashed_pw, session['user_id']))
        db.commit()
        return render_template('cambia_password.html', msg="Password aggiornata con successo!")
    return render_template('cambia_password.html')

@app.route('/aggiorna_stato/<int:id>', methods=['POST'])
def aggiorna_stato(id):
    if session.get('ruolo') != 'admin': return redirect(url_for('segnalazioni'))
    nuovo_stato = request.form.get('stato')
    db.execute("UPDATE segnalazioni SET stato = ? WHERE id_segnalazione = ?", (nuovo_stato, id))
    db.commit()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id>', methods=['POST'])
def elimina_segnalazione(id):
    if session.get('ruolo') != 'admin': return redirect(url_for('segnalazioni'))
    db.execute("DELETE FROM segnalazioni WHERE id_segnalazione = ?", (id,))
    db.commit()
    return redirect(url_for('segnalazioni'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
