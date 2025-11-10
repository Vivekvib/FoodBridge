import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'final_demo_key_xyz'
DB_NAME = 'foodbridge.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_NAME):
        with app.app_context():
            db = get_db()
            with open('schema.sql', mode='r') as f:
                db.cursor().executescript(f.read())
            db.commit()
            print("DB Initialized.")

@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        db = get_db()
        count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', 
                          (session['user_id'],)).fetchone()[0]
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
            db = get_db()
            db.execute("INSERT INTO users (username, password, role, phone) VALUES (?, ?, ?, ?)",
                       (request.form['username'], hashed_pw, request.form['role'], request.form['phone']))
            db.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already taken.", "danger")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (request.form['username'],)).fetchone()
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
def index(): return render_template('index.html')

@app.route('/donor', methods=['GET', 'POST'])
@login_required
def donor():
    if session['role'] != 'donor': 
        flash("Access Denied: You are logged in as an NGO.", "warning")
        return redirect(url_for('index'))
        
    db = get_db()
    if request.method == 'POST':
        cursor = db.execute('INSERT INTO donations (donor_id, org_name, food_item, quantity, expiry_datetime) VALUES (?, ?, ?, ?, ?)',
                     (session['user_id'], request.form['org_name'], request.form['food_item'], request.form['quantity'], request.form['expiry']))
        new_donation_id = cursor.lastrowid
        
        # NOTIFY ALL NGOs about new donation
        ngos = db.execute("SELECT id FROM users WHERE role = 'ngo'").fetchall()
        for ngo in ngos:
             msg = f"New Donation Alert: {request.form['food_item']} from {request.form['org_name']}"
             db.execute('INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)',
                        (ngo['id'], msg, 'new_donation', new_donation_id))
        
        db.commit()
        flash('Donation listed! NGOs have been notified.', 'success')
        
    my_donations = db.execute('SELECT * FROM donations WHERE donor_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    return render_template('donor.html', my_donations=my_donations)

@app.route('/ngo')
@login_required
def ngo():
    if session['role'] != 'ngo': 
        flash("Access Denied: You are logged in as a Donor.", "warning")
        return redirect(url_for('index'))
        
    db = get_db()
    donations = db.execute('SELECT * FROM donations WHERE status = "Active" ORDER BY created_at DESC').fetchall()
    my_claims = db.execute('SELECT d.*, u.username as donor_name FROM donations d JOIN users u ON d.donor_id = u.id WHERE claimed_by = ? ORDER BY d.created_at DESC', (session['user_id'],)).fetchall()
    return render_template('ngo.html', donations=donations, my_claims=my_claims)

@app.route('/claim/<int:id>', methods=['POST'])
@login_required
def claim(id):
    if session['role'] != 'ngo': return redirect(url_for('index'))
    db = get_db()
    donation = db.execute('SELECT donor_id, food_item FROM donations WHERE id = ?', (id,)).fetchone()
    db.execute('UPDATE donations SET status = "Claimed", claimed_by = ? WHERE id = ?', (session['user_id'], id))
    
    # Notify Donor of claim
    msg = f"Great news! Your {donation['food_item']} was claimed by {session['username']}."
    db.execute('INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)', 
               (donation['donor_id'], msg, 'claim', id))
    db.commit()
    
    flash('Claimed! Check "My Claims" to chat with the donor.', 'success')
    return redirect(url_for('ngo'))

# --- NOTIFICATIONS & CHAT ---
@app.route('/notifications')
@login_required
def notifications():
    db = get_db()
    notifs = db.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    return render_template('notifications.html', notifs=notifs)

@app.route('/notification/read/<int:notif_id>')
@login_required
def read_notification(notif_id):
    db = get_db()
    notif = db.execute('SELECT * FROM notifications WHERE id = ? AND user_id = ?', (notif_id, session['user_id'])).fetchone()
    
    if notif:
        # Mark as read
        db.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notif_id,))
        db.commit()
        
        # Smart Redirect based on type
        if notif['type'] == 'chat' or notif['type'] == 'claim':
             return redirect(url_for('chat', donation_id=notif['related_id']))
        elif notif['type'] == 'new_donation':
             return redirect(url_for('ngo'))
             
    return redirect(url_for('notifications'))

@app.route('/chat/<int:donation_id>', methods=['GET', 'POST'])
@login_required
def chat(donation_id):
    db = get_db()
    donation = db.execute('SELECT * FROM donations WHERE id = ?', (donation_id,)).fetchone()
    
    if request.method == 'POST':
        db.execute('INSERT INTO messages (donation_id, sender_id, text) VALUES (?, ?, ?)',
                   (donation_id, session['user_id'], request.form['message']))
        
        # Send CHAT Notification to the OTHER person
        recipient_id = donation['claimed_by'] if session['user_id'] == donation['donor_id'] else donation['donor_id']
        msg = f"New message from {session['username']} regarding {donation['food_item']}"
        db.execute('INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)',
                   (recipient_id, msg, 'chat', donation_id))
                   
        db.commit()
        return redirect(url_for('chat', donation_id=donation_id))
    
    messages = db.execute('SELECT m.*, u.username FROM messages m JOIN users u ON m.sender_id = u.id WHERE donation_id = ? ORDER BY m.created_at', (donation_id,)).fetchall()
    return render_template('chat.html', donation=donation, messages=messages)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)