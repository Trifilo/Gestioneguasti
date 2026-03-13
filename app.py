from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from functools import wraps
import os
import re
import string
import random

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave_segreta_scuola_2026')
DB_NAME = 'scuola.db'

# ===============================
# CONFIGURAZIONE DATABASE
# ===============================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def valida_password(password):
    """Verifica: min 8 caratteri, una maiuscola, un numero."""
    if len(password) < 8 or not re.search("[A-Z]", password) or not re.search("[0-9]", password):
        return False
    return True

def genera_password_casuale(lunghezza=10):
    """Genera una password casuale che rispetta i requisiti di validazione."""
    caratteri = string.ascii_letters + string.digits + "!@#$%&"
    while True:
        pwd = ''.join(random.choice(caratteri) for i in range(lunghezza))
        # Assicuriamoci che la password temporanea superi il nostro stesso controllo
        if valida_password(pwd):
            return pwd

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Tabella Utenti
    c.execute("""CREATE TABLE IF NOT EXISTS utenti (
        id_utente INTEGER PRIMARY KEY AUTOINCREMENT, 
        nome TEXT, 
        email TEXT UNIQUE, 
        password TEXT, 
        ruolo TEXT DEFAULT 'studente')""")
    
    # Tabella Segnalazioni
    c.execute("""CREATE TABLE IF NOT EXISTS segnalazioni (
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
    
    # Creazione Admin predefinito se non esiste
    c.execute("SELECT * FROM utenti WHERE email='admin@scuola.it'")
    if not c.fetchone():
        c.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", 
                 ('Admin','admin@scuola.it','Admin123!','admin'))
    conn.commit()
    conn.close()

init_db()

# ===============================
# DECORATORI DI SICUREZZA
# ===============================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ===============================
# GESTIONE ACCESSI
# ===============================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session.update({'user_id': user['id_utente'], 'ruolo': user['ruolo'], 'nome': user['nome']})
            return redirect(url_for('index'))
        return render_template('login.html', errore="Credenziali non valide. Riprova.")
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nome, email, password = request.form.get('nome'), request.form.get('email'), request.form.get('password')
        if not valida_password(password):
            return render_template('register.html', errore="La password deve avere almeno 8 caratteri, una maiuscola e un numero.")
        
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", (nome,email,password,'studente'))
            conn.commit()
            return redirect(url_for('login'))
        except:
            return render_template('register.html', errore="Questa email è già registrata.")
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/recupera', methods=['GET', 'POST'])
def recupera():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM utenti WHERE email=?", (email,)).fetchone()
        if user:
            # Genera password casuale
            nuova_password = genera_password_casuale()
            conn.execute("UPDATE utenti SET password=? WHERE email=?", (nuova_password, email))
            conn.commit()
            conn.close()
            # Mostra la password casuale all'utente
            messaggio = f"Password resettata! La tua nuova password temporanea è: {nuova_password}"
            return render_template('recupera.html', msg=messaggio)
        conn.close()
        return render_template('recupera.html', errore="Email non trovata.")
    return render_template('recupera.html')

@app.route('/cambia_password', methods=['GET', 'POST'])
@login_required
def cambia_password():
    if request.method == 'POST':
        nuova_password = request.form.get('nuova_password')
        
        if not valida_password(nuova_password):
            return render_template('cambia_password.html', errore="La password deve avere almeno 8 caratteri, una maiuscola e un numero.")
        
        conn = get_db_connection()
        # Aggiorniamo la password dell'utente loggato
        conn.execute("UPDATE utenti SET password=? WHERE id_utente=?", (nuova_password, session['user_id']))
        conn.commit()
        conn.close()
        return render_template('cambia_password.html', msg="Password personale aggiornata con successo! Ora puoi usare questa per i futuri accessi.")
        
    return render_template('cambia_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ===============================
# CUORE ASINCRONO (POLLING)
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
    if session.get('ruolo') == 'admin':
        query = "SELECT s.*, u.nome as nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente ORDER BY s.data DESC"
        res = conn.execute(query).fetchall()
    else:
        query = "SELECT s.*, u.nome as nome_utente FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente WHERE s.id_utente=? ORDER BY s.data DESC"
        res = conn.execute(query, (session['user_id'],)).fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in res])

# ===============================
# AZIONI SEGNALAZIONI
# ===============================
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
        conn.execute("INSERT INTO segnalazioni (titolo,descrizione,categoria,classe,aula,id_utente) VALUES (?,?,?,?,?,?)", dati)
        conn.commit()
        conn.close()
        return redirect(url_for('segnalazioni'))
    return render_template('nuova_segnalazione.html')

@app.route('/aggiorna_stato/<int:id>', methods=['POST'])
@login_required
def aggiorna_stato(id):
    if session.get('ruolo') != 'admin': return "Negato", 403
    nuovo_stato = request.form.get('stato')
    conn = get_db_connection()
    conn.execute("UPDATE segnalazioni SET stato=? WHERE id_segnalazione=?", (nuovo_stato, id))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id>', methods=['POST'])
@login_required
def elimina_segnalazione(id):
    if session.get('ruolo') != 'admin': return "Negato", 403
    conn = get_db_connection()
    conn.execute("DELETE FROM segnalazioni WHERE id_segnalazione=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
