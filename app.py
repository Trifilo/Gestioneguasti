from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps
import os
import re
import string
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Prende la chiave da Render, altrimenti usa quella di default
app.secret_key = os.environ.get('SECRET_KEY', 'chiave_segreta_scuola_2026')

# ===============================
# CONFIGURAZIONE DATABASE
# ===============================
def get_db_connection():
    # DATABASE_URL è la variabile che Render ti fornirà automaticamente
    db_url = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Tabella Utenti (Usa SERIAL per PostgreSQL invece di AUTOINCREMENT)
    cur.execute("""CREATE TABLE IF NOT EXISTS utenti (
        id_utente SERIAL PRIMARY KEY, 
        nome TEXT, 
        email TEXT UNIQUE, 
        password TEXT, 
        ruolo TEXT DEFAULT 'studente')""")
    
    # Tabella Segnalazioni
    cur.execute("""CREATE TABLE IF NOT EXISTS segnalazioni (
        id_segnalazione SERIAL PRIMARY KEY, 
        titolo TEXT, 
        descrizione TEXT, 
        categoria TEXT, 
        classe TEXT, 
        aula TEXT, 
        stato TEXT DEFAULT 'rosso', 
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        id_utente INTEGER REFERENCES utenti(id_utente))""")
    
    # Creazione Admin predefinito se non esiste (Password: Admin123!)
    cur.execute("SELECT * FROM utenti WHERE email='admin@scuola.it'")
    if not cur.fetchone():
        hashed_pw = generate_password_hash('Admin123!')
        cur.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (%s,%s,%s,%s)", 
                 ('Admin','admin@scuola.it', hashed_pw, 'admin'))
    
    conn.commit()
    cur.close()
    conn.close()

# Inizializzazione automatica al primo avvio
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Errore inizializzazione DB: {e}")

# ===============================
# UTILITY E SICUREZZA
# ===============================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def valida_password(password):
    if len(password) < 8 or not re.search("[A-Z]", password) or not re.search("[0-9]", password):
        return False
    return True

def genera_password_casuale(lunghezza=10):
    caratteri = string.ascii_letters + string.digits + "!@#$%&"
    return ''.join(random.choice(caratteri) for i in range(lunghezza))

# ===============================
# GESTIONE ACCESSI
# ===============================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM utenti WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session.update({'user_id': user['id_utente'], 'ruolo': user['ruolo'], 'nome': user['nome']})
            return redirect(url_for('index'))
        return render_template('login.html', errore="Credenziali non valide.")
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nome, email, password = request.form.get('nome'), request.form.get('email'), request.form.get('password')
        if not valida_password(password):
            return render_template('register.html', errore="Password non valida (min 8 car, 1 Maiusc, 1 Num).")
        
        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (%s,%s,%s,%s)", (nome,email,hashed_pw,'studente'))
            conn.commit()
            return redirect(url_for('login'))
        except:
            return render_template('register.html', errore="Email già registrata.")
        finally:
            cur.close()
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ===============================
# SEGNALAZIONI E POLLING
# ===============================
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
    cur = conn.cursor()
    if session.get('ruolo') == 'admin':
        query = "SELECT s.*, u.nome as nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente ORDER BY s.data DESC"
        cur.execute(query)
    else:
        query = "SELECT s.*, u.nome as nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente WHERE s.id_utente=%s ORDER BY s.data DESC"
        cur.execute(query, (session['user_id'],))
    res = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(res)

@app.route('/nuova_segnalazione', methods=['GET','POST'])
@login_required
def nuova_segnalazione():
    if request.method == 'POST':
        dati = (
            request.form.get('titolo'),
            request.form.get('descrizione'),
            request.form.get('categoria'),
            request.form.get('classe'),
            request.form.get('aula'),
            session['user_id']
        )
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO segnalazioni (titolo,descrizione,categoria,classe,aula,id_utente) VALUES (%s,%s,%s,%s,%s,%s)", dati)
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('segnalazioni'))
    return render_template('nuova_segnalazione.html')

@app.route('/aggiorna_stato/<int:id>', methods=['POST'])
@login_required
def aggiorna_stato(id):
    if session.get('ruolo') != 'admin': return "Negato", 403
    nuovo_stato = request.form.get('stato')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE segnalazioni SET stato=%s WHERE id_segnalazione=%s", (nuovo_stato, id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id>', methods=['POST'])
@login_required
def elimina_segnalazione(id):
    if session.get('ruolo') != 'admin': return "Negato", 403
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM segnalazioni WHERE id_segnalazione=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('segnalazioni'))

if __name__ == '__main__':
    app.run()
