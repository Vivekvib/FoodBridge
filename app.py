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
    
    # 1. First, create tables if they don't exist yet
    cursor.execute(schema_sql)
    conn.commit()

    # 2. Safely attach new columns to existing donations table
    donations_alter = [
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'Cooked Veg';",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS unit VARCHAR(30) DEFAULT 'Servings';",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS packaging_note VARCHAR(100) DEFAULT 'Not specified';",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS address TEXT DEFAULT 'Address not provided';",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION NULL;",
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION NULL;",
        "ALTER TABLE donations ALTER COLUMN quantity TYPE INTEGER USING (COALESCE(NULLIF(REGEXP_REPLACE(quantity::text, '[^0-9]', '', 'g'), ''), '0')::integer);"
    ]
    for q in donations_alter:
        try:
            cursor.execute(q)
            conn.commit()
        except Exception:
            conn.rollback()

    # 3. NEW: Safely attach Profile & Verification columns to the Users table
    users_alter = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_address TEXT;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS description TEXT;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified INTEGER DEFAULT 0;"
    ]
    for q in users_alter:
        try:
            cursor.execute(q)
            conn.commit()
        except Exception:
            conn.rollback()
            
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

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Grab the updated info from the form
        phone = request.form.get('phone')
        default_address = request.form.get('default_address')
        description = request.form.get('description')
        
        # Update the user's record in the database
        execute_query(
            "UPDATE users SET phone = ?, default_address = ?, description = ? WHERE id = ?",
            (phone, default_address, description, session['user_id']),
            commit=True
        )
        flash("Profile updated successfully! ✅", "success")
        return redirect(url_for('profile'))

    # GET request: fetch the user's current data to display in the form
    user = execute_query(
        "SELECT * FROM users WHERE id = ?", 
        (session['user_id'],), 
        fetchone=True
    )
    return render_template('profile.html', user=user)

@app.route('/donor', methods=['GET', 'POST'])
@login_required
def donor():
    if session.get('role') != 'donor':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Grab structured form fields
        org_name = request.form.get('org_name')
        food_item = request.form.get('food_item')
        category = request.form.get('category', 'Cooked Veg')
        
        # Ensure quantity is stored as a clean integer
        try:
            quantity = int(request.form.get('quantity', 0))
        except ValueError:
            quantity = 0
            
        unit = request.form.get('unit', 'Servings')
        packaging_note = request.form.get('packaging_note', 'Not specified')
        address = request.form.get('address', 'Address not provided')
        expiry = request.form.get('expiry')
        
        # Optional GPS coordinates from hidden form fields
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        lat_val = float(latitude) if latitude and latitude.strip() else None
        lng_val = float(longitude) if longitude and longitude.strip() else None

        if quantity <= 0:
            flash("Please enter a valid quantity greater than 0.", "warning")
            return redirect(url_for('donor'))

        # Insert new structured listing into database
        insert_query = """
            INSERT INTO donations 
            (donor_id, org_name, food_item, category, quantity, unit, packaging_note, address, latitude, longitude, expiry_datetime, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
        """
        execute_query(
            insert_query,
            (
                session['user_id'],
                org_name,
                food_item,
                category,
                quantity,
                unit,
                packaging_note,
                address,
                lat_val,
                lng_val,
                expiry
            ),
            commit=True
        )

        flash("Donation listed live with structured logistics data! 🚀", "success")
        return redirect(url_for('donor'))

    # GET request: fetch existing donations for this donor (FIXED: fetchall=True)
    my_donations = execute_query(
        "SELECT * FROM donations WHERE donor_id = ? ORDER BY id DESC",
        (session['user_id'],),
        fetchall=True
    )
    return render_template('donor.html', my_donations=my_donations)

@app.route('/ngo')
@login_required
def ngo():
    # Safe dictionary get to avoid KeyError if role is missing from session
    if session.get('role') != 'ngo': 
        flash("Access Denied: You are logged in as a Donor.", "warning")
        return redirect(url_for('index'))
        
    # 1. Case-insensitive check to ensure only active listings appear on the market feed
    donations = execute_query(
        "SELECT * FROM donations WHERE LOWER(status) = 'active' ORDER BY created_at DESC", 
        fetchall=True
    )
    
    # 2. Fetch claims made by this specific NGO, joining donor username
    my_claims = execute_query(
        """
        SELECT d.*, u.username as donor_name 
        FROM donations d 
        JOIN users u ON d.donor_id = u.id 
        WHERE d.claimed_by = ? 
        ORDER BY d.created_at DESC
        """, 
        (session['user_id'],), 
        fetchall=True
    )
    
    # 3. Prevent 500 errors by safely casting PostgreSQL datetime objects to strings
    safe_donations = []
    if donations:
        for d in donations:
            d_dict = dict(d)
            if d_dict.get('created_at') is not None:
                d_dict['created_at'] = str(d_dict['created_at'])
            if d_dict.get('expiry_datetime') is not None:
                d_dict['expiry_datetime'] = str(d_dict['expiry_datetime'])
            safe_donations.append(d_dict)
            
    safe_claims = []
    if my_claims:
        for c in my_claims:
            c_dict = dict(c)
            if c_dict.get('created_at') is not None:
                c_dict['created_at'] = str(c_dict['created_at'])
            if c_dict.get('expiry_datetime') is not None:
                c_dict['expiry_datetime'] = str(c_dict['expiry_datetime'])
            safe_claims.append(c_dict)

    return render_template('ngo.html', donations=safe_donations, my_claims=safe_claims)

@app.route('/claim/<int:id>', methods=['POST'])
@login_required
def claim(id):
    if session.get('role') != 'ngo':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('index'))

    # 1. Fetch the active donation listing
    donation = execute_query(
        "SELECT * FROM donations WHERE id = ? AND LOWER(status) = 'active'",
        (id,),
        fetchone=True
    )
    if not donation:
        flash("This donation is no longer active or has already been claimed.", "warning")
        return redirect(url_for('ngo'))

    original_qty = int(donation['quantity'])
    
    # 2. Grab and validate the requested claim quantity
    try:
        claim_qty = int(request.form.get('claim_quantity', original_qty))
    except (ValueError, TypeError):
        claim_qty = original_qty

    if claim_qty <= 0 or claim_qty > original_qty:
        flash(f"Please enter a valid quantity between 1 and {original_qty}.", "warning")
        return redirect(url_for('ngo'))

    # 3. SPLIT-LISTING LOGIC
    if claim_qty == original_qty:
        # Full claim: simply update the existing listing
        execute_query(
            "UPDATE donations SET status = 'Claimed', claimed_by = ? WHERE id = ?",
            (session['user_id'], id),
            commit=True
        )
        msg = f"Great news! Your entire listing of {claim_qty} {donation['unit']} of {donation['food_item']} was claimed by {session['username']}."
    else:
        # Partial claim: update original record to 'Claimed' for claim_qty
        remaining_qty = original_qty - claim_qty
        
        execute_query(
            "UPDATE donations SET quantity = ?, status = 'Claimed', claimed_by = ? WHERE id = ?",
            (claim_qty, session['user_id'], id),
            commit=True
        )
        
        # Generate a new 'Active' record for the remaining balance
        split_insert_query = """
            INSERT INTO donations 
            (donor_id, org_name, food_item, category, quantity, unit, packaging_note, address, latitude, longitude, expiry_datetime, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
        """
        execute_query(
            split_insert_query,
            (
                donation['donor_id'],
                donation['org_name'],
                donation['food_item'],
                donation['category'],
                remaining_qty,
                donation['unit'],
                donation['packaging_note'],
                donation['address'],
                donation['latitude'],
                donation['longitude'],
                donation['expiry_datetime']
            ),
            commit=True
        )
        msg = f"Good news! {session['username']} claimed {claim_qty} {donation['unit']} of your {donation['food_item']}. The remaining {remaining_qty} {donation['unit']} is still listed live!"

    # 4. Send notification to the Donor
    execute_query(
        "INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)",
        (donation['donor_id'], msg, 'claim', id),
        commit=True
    )

    flash(f"Successfully claimed {claim_qty} {donation['unit']}! Check 'My Claims' to chat with the donor.", "success")
    return redirect(url_for('ngo'))

@app.route('/delete_donation/<int:donation_id>', methods=['POST'])
@login_required
def delete_donation(donation_id):
    if session.get('role') != 'donor':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    # Only delete if it belongs to this donor AND is still active
    execute_query(
        "DELETE FROM donations WHERE id = ? AND donor_id = ? AND LOWER(status) = 'active'",
        (donation_id, session['user_id']),
        commit=True
    )
    flash("Active listing removed successfully.", "info")
    return redirect(url_for('donor'))
    
# --- NOTIFICATIONS & CHAT ---
@app.route('/notifications')
@login_required
def notifications():
    notifs = execute_query(
        'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', 
        (session['user_id'],), 
        fetchall=True
    )
    
    # Safely convert datetime timestamps to strings for Jinja rendering
    safe_notifs = []
    if notifs:
        for n in notifs:
            n_dict = dict(n)
            if 'created_at' in n_dict and n_dict['created_at'] is not None:
                n_dict['created_at'] = str(n_dict['created_at'])
            safe_notifs.append(n_dict)
            
    return render_template('notifications.html', notifs=safe_notifs)


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
    
    # Safety check: prevent crash if donation was deleted or doesn't exist
    if not donation:
        flash("Donation not found.", "danger")
        return redirect(url_for('index'))

    execute_query(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND related_id = ? AND type = 'chat'",
        (session['user_id'], donation_id),
        commit=True)
    if request.method == 'POST':
        try:
            # Safely grab message text whether input name is 'message' or 'text'
            msg_text = request.form.get('message') or request.form.get('text')
            if not msg_text:
                flash("Message cannot be empty.", "warning")
                return redirect(url_for('chat', donation_id=donation_id))

            # 1. Insert the chat message
            execute_query(
                'INSERT INTO messages (donation_id, sender_id, text) VALUES (?, ?, ?)',
                (donation_id, session['user_id'], msg_text),
                commit=True
            )
            
            # 2. Determine recipient safely (fallback to donor if claimed_by is None)
            recipient_id = donation['claimed_by'] if session['user_id'] == donation['donor_id'] else donation['donor_id']
            
            # Only send notification if a valid recipient exists and is not the sender
            if recipient_id and recipient_id != session['user_id']:
                notif_msg = f"New message from {session['username']} regarding {donation['food_item']}"
                execute_query(
                    'INSERT INTO notifications (user_id, message, type, related_id) VALUES (?, ?, ?, ?)',
                    (recipient_id, notif_msg, 'chat', donation_id),
                    commit=True
                )
                
            return redirect(url_for('chat', donation_id=donation_id))
            
        except Exception as e:
            print(f"CHAT POST ERROR: {e}")
            flash(f"Error sending message: {e}", "danger")
            return redirect(url_for('chat', donation_id=donation_id))
    
    messages = execute_query(
        'SELECT m.*, u.username FROM messages m JOIN users u ON m.sender_id = u.id WHERE donation_id = ? ORDER BY m.created_at', 
        (donation_id,), 
        fetchall=True
    )
    
    # FIX: Ensure messages are mutable dicts and convert PostgreSQL datetime timestamps to strings
    safe_messages = []
    if messages:
        for m in messages:
            msg_dict = dict(m)
            if 'created_at' in msg_dict and msg_dict['created_at'] is not None:
                msg_dict['created_at'] = str(msg_dict['created_at'])
            safe_messages.append(msg_dict)
            
    return render_template('chat.html', donation=donation, messages=safe_messages)
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

@app.route('/api/notifications/count')
@login_required
def api_notif_count():
    row = execute_query(
        'SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0', 
        (session['user_id'],), 
        fetchone=True
    )
    count = row['count'] if row else 0
    return {'count': count}

if __name__ == '__main__':
    app.run(debug=True)