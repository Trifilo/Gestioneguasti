from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave_segreta_scuola_2026')
DB_NAME = 'scuola.db'

# ===============================
# FUNZIONI DI SUPPORTO E DATABASE
# ===============================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def valida_password(password):
    """Verifica: almeno 8 caratteri, una maiuscola e un numero."""
    if len(password) < 8:
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
        return False
    return True

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            id_utente INTEGER PRIMARY KEY AUTOINCREMENT, 
            nome TEXT, 
            email TEXT UNIQUE, 
            password TEXT, 
            ruolo TEXT DEFAULT 'studente'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS segnalazioni (
            id_segnalazione INTEGER PRIMARY KEY AUTOINCREMENT, 
            titolo TEXT, 
            descrizione TEXT, 
            categoria TEXT, 
            classe TEXT, 
            aula TEXT, 
            stato TEXT DEFAULT 'rosso', 
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            id_utente INTEGER, 
            FOREIGN KEY (id_utente) REFERENCES utenti(id_utente)
        )
    """)
    # Creazione Admin di default se non esiste
    c.execute("SELECT * FROM utenti WHERE email='admin@scuola.it'")
    if not c.fetchone():
        c.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", 
                 ('Amministratore','admin@scuola.it','Admin123!','admin'))
    conn.commit()
    conn.close()

init_db()

# ===============================
# DECORATORI DI PROTEZIONE
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
        if str(session.get('ruolo')).lower() != 'admin':
            return "Accesso negato: Area riservata agli amministratori", 403
        return f(*args, **kwargs)
    return decorated

# ===============================
# AUTENTICAZIONE E REGISTRAZIONE
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
        return "<h3>Credenziali errate</h3><a href='/login'>Riprova</a>"
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not valida_password(password):
            return "<h3>Errore: La password deve avere almeno 8 caratteri, una maiuscola e un numero.</h3><a href='/register'>Riprova</a>"
            
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO utenti (nome,email,password,ruolo) VALUES (?,?,?,?)", (nome,email,password,'studente'))
            conn.commit()
            return redirect(url_for('login'))
        except:
            return "<h3>Email già registrata</h3><a href='/register'>Riprova</a>"
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ===============================
# RECUPERO PASSWORD (Risolve l'errore dello screenshot)
# ===============================
@app.route('/recupera', methods=['GET', 'POST'])
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
            return f"<h3>Password resettata!</h3> Nuova password: <b>{nuova_pw}</b><br><a href='/login'>Accedi</a>"
        conn.close()
        return "<h3>Email non trovata</h3><a href='/recupera'>Riprova</a>"
    
    return '''
        <div style="font-family:sans-serif; margin:50px; max-width:400px;">
            <h2>Recupero Password</h2>
            <p>Inserisci la tua email per ricevere una password temporanea.</p>
            <form method="POST">
                <input type="email" name="email" placeholder="Email" required style="width:100%; padding:10px; margin-bottom:10px;">
                <button type="submit" style="width:100%; padding:10px; background:#007bff; color:white; border:none; cursor:pointer;">Invia Nuova Password</button>
            </form>
            <br><a href="/login">Torna al Login</a>
        </div>
    '''

# ===============================
# SEGNALAZIONI (UTENTE E ADMIN)
# ===============================
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/segnalazioni')
@login_required
def segnalazioni():
    conn = get_db_connection()
    ruolo = str(session.get('ruolo')).lower()
    if ruolo == 'admin':
        # Admin vede tutto
        res = conn.execute("SELECT s.*, u.nome FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente ORDER BY s.data DESC").fetchall()
    else:
        # Studente vede solo le sue
        res = conn.execute("SELECT s.*, u.nome FROM segnalazioni s JOIN utenti u ON s.id_utente = u.id_utente WHERE s.id_utente=? ORDER BY s.data DESC", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('segnalazioni.html', segnalazioni=res)

@app.route('/nuova_segnalazione', methods=['GET','POST'])
@login_required
def nuova_segnalazione():
    if request.method == 'POST':
        titolo = request.form.get('titolo', 'Senza titolo')
        descrizione = request.form.get('descrizione', '-')
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
            return f"Errore Database: {str(e)}"
            
    return render_template('nuova_segnalazione.html')

# ===============================
# AZIONI ADMIN
# ===============================
@app.route('/aggiorna_stato/<int:id>', methods=['POST'])
@admin_required
def aggiorna_stato(id):
    stato = request.form.get('stato')
    conn = get_db_connection()
    conn.execute("UPDATE segnalazioni SET stato=? WHERE id_segnalazione=?", (stato, id))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/elimina_segnalazione/<int:id>', methods=['POST'])
@admin_required
def elimina_segnalazione(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM segnalazioni WHERE id_segnalazione=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('segnalazioni'))

@app.route('/profilo')
@login_required
def profilo():
    return f"<h3>Profilo di {session.get('nome')}</h3><p>Ruolo: {session.get('ruolo')}</p><a href='/'>Indietro</a>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)