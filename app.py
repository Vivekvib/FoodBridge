import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = 'final_demo_key_xyz'
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if DATABASE_URL:
        # Fix Render URL protocol format for psycopg2 if needed
        db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    else:
        # Local SQLite fallback for offline development
        conn = sqlite3.connect('foodbridge.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    with open('schema.sql', 'r') as f:
        schema_sql = f.read()

    conn = get_db()
    cursor = conn.cursor()
    
    # psycopg2 executes multi-statement SQL strings seamlessly
    cursor.execute(schema_sql)
    conn.commit()
    
    cursor.close()
    conn.close()
    
def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False, return_id=False):
    """
    Helper function to abstract SQL query execution across SQLite and PostgreSQL.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Adapt SQL placeholders for the underlying database backend
    if DATABASE_URL:
        formatted_query = query.replace('?', '%s')
        if return_id:
            formatted_query += " RETURNING id"
    else:
        formatted_query = query

    cursor.execute(formatted_query, params)
    
    result = None
    if return_id:
        if DATABASE_URL:
            row = cursor.fetchone()
            result = row['id'] if isinstance(row, dict) else row[0]
        else:
            result = cursor.lastrowid
    elif fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()

    if commit:
        conn.commit()

    cursor.close()
    conn.close()
    return result

@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        row = execute_query(
            'SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0', 
            (session['user_id'],), 
            fetchone=True
        )
        count = row['count'] if row else 0
        return dict(notif_count=count)
    return dict(notif_count=0)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- AUTH ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        try:
            execute_query(
                "INSERT INTO users (username, password, role, phone) VALUES (?, ?, ?, ?)",
                (request.form['username'], hashed_pw, request.form['role'], request.form['phone']),
                commit=True
            )
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            print(f"CRITICAL REGISTRATION ERROR: {e}")
            flash(f"DEBUG ERROR: {e}", "danger")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = execute_query(
            "SELECT * FROM users WHERE username = ?", 
            (request.form['username'],), 
            fetchone=True
        )
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        flash("Invalid credentials.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- MAIN ROUTES ---
@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/donor', methods=['GET', 'POST'])
@login_required
def donor():
    if session['role'] != 'donor': 
        flash("Access Denied: You are logged in as an NGO.", "warning")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        new_donation_id = execute_query(
            'INSERT INTO donations (donor_id, org_name, food_item, quantity, expiry_datetime) VALUES (?, ?, ?, ?, ?)',
            (session['user_id'], request.form['org_name'], request.form['food_item'], request.form['quantity'], request.form['expiry']),
            commit=True,
            return_id=True
        )
        
        # NOTIFY ALL NGOs about new donation
        ngos = execute_query("SELECT id FROM users WHERE role = 'ngo'", fetchall=True)
        for ngo in ngos:
            msg = f"New Donation Alert: {request.form['food_item']} from {request.form['org_name']}"
            execute_query(
                'INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)',
                (ngo['id'], msg, 'new_donation', new_donation_id),
                commit=True
            )
        
        flash('Donation listed! NGOs have been notified.', 'success')
        
    my_donations = execute_query(
        'SELECT * FROM donations WHERE donor_id = ? ORDER BY created_at DESC', 
        (session['user_id'],), 
        fetchall=True
    )
    return render_template('donor.html', my_donations=my_donations)

@app.route('/ngo')
@login_required
def ngo():
    if session['role'] != 'ngo': 
        flash("Access Denied: You are logged in as a Donor.", "warning")
        return redirect(url_for('index'))
        
    donations = execute_query(
        "SELECT * FROM donations WHERE status = 'Active' ORDER BY created_at DESC", 
        fetchall=True
    )
    my_claims = execute_query(
        'SELECT d.*, u.username as donor_name FROM donations d JOIN users u ON d.donor_id = u.id WHERE claimed_by = ? ORDER BY d.created_at DESC', 
        (session['user_id'],), 
        fetchall=True
    )
    return render_template('ngo.html', donations=donations, my_claims=my_claims)

@app.route('/claim/<int:id>', methods=['POST'])
@login_required
def claim(id):
    if session['role'] != 'ngo': 
        return redirect(url_for('index'))
        
    donation = execute_query(
        'SELECT donor_id, food_item FROM donations WHERE id = ?', 
        (id,), 
        fetchone=True
    )
    execute_query(
        "UPDATE donations SET status = 'Claimed', claimed_by = ? WHERE id = ?", 
        (session['user_id'], id), 
        commit=True
    )
    
    # Notify Donor of claim
    msg = f"Great news! Your {donation['food_item']} was claimed by {session['username']}."
    execute_query(
        'INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)', 
        (donation['donor_id'], msg, 'claim', id), 
        commit=True
    )
    
    flash('Claimed! Check "My Claims" to chat with the donor.', 'success')
    return redirect(url_for('ngo'))

# --- NOTIFICATIONS & CHAT ---
@app.route('/notifications')
@login_required
def notifications():
    notifs = execute_query(
        'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', 
        (session['user_id'],), 
        fetchall=True
    )
    return render_template('notifications.html', notifs=notifs)

@app.route('/notification/read/<int:notif_id>')
@login_required
def read_notification(notif_id):
    notif = execute_query(
        'SELECT * FROM notifications WHERE id = ? AND user_id = ?', 
        (notif_id, session['user_id']), 
        fetchone=True
    )
    
    if notif:
        execute_query(
            'UPDATE notifications SET is_read = 1 WHERE id = ?', 
            (notif_id,), 
            commit=True
        )
        
        if notif['type'] in ('chat', 'claim'):
            return redirect(url_for('chat', donation_id=notif['related_id']))
        elif notif['type'] == 'new_donation':
            return redirect(url_for('ngo'))
             
    return redirect(url_for('notifications'))

@app.route('/chat/<int:donation_id>', methods=['GET', 'POST'])
@login_required
def chat(donation_id):
    donation = execute_query(
        'SELECT * FROM donations WHERE id = ?', 
        (donation_id,), 
        fetchone=True
    )
    
    if request.method == 'POST':
        execute_query(
            'INSERT INTO messages (donation_id, sender_id, text) VALUES (?, ?, ?)',
            (donation_id, session['user_id'], request.form['message']),
            commit=True
        )
        
        recipient_id = donation['claimed_by'] if session['user_id'] == donation['donor_id'] else donation['donor_id']
        msg = f"New message from {session['username']} regarding {donation['food_item']}"
        execute_query(
            'INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)',
            (recipient_id, msg, 'chat', donation_id),
            commit=True
        )
        return redirect(url_for('chat', donation_id=donation_id))
    
    messages = execute_query(
        'SELECT m.*, u.username FROM messages m JOIN users u ON m.sender_id = u.id WHERE donation_id = ? ORDER BY m.created_at', 
        (donation_id,), 
        fetchall=True
    )
    return render_template('chat.html', donation=donation, messages=messages)

@app.route('/init-db-now')
def force_init_db():
    try:
        init_db()
        return "Database tables created successfully!"
    except Exception as e:
        return f"Error initializing database: {e}"

# --- AUTOMATIC TABLE INITIALIZATION ON GUNICORN/FLASK STARTUP ---
with app.app_context():
    try:
        init_db()
        print("Database schema initialized successfully on startup.")
    except Exception as e:
        print(f"Startup DB init log/warning: {e}")

if __name__ == '__main__':
    app.run(debug=True)