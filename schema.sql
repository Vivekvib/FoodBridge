DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS donations;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS messages;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    phone TEXT
);

CREATE TABLE donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL,
    org_name TEXT NOT NULL,
    food_item TEXT NOT NULL,
    quantity TEXT NOT NULL,
    expiry_datetime TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active',
    claimed_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_id) REFERENCES users (id),
    FOREIGN KEY (claimed_by) REFERENCES users (id)
);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL,         -- 'system', 'chat', 'claim', 'new_donation'
    related_id INTEGER,         -- ID of related donation (for redirection)
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donation_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donation_id) REFERENCES donations (id),
    FOREIGN KEY (sender_id) REFERENCES users (id)
);

-- DUMMY DATA
INSERT INTO users (username, password, role, phone) VALUES 
('demodonor', 'scrypt:32768:8:1$lP7t9X8a9b8c$e8d9c0...', 'donor', '9876543210'),
('demongo', 'scrypt:32768:8:1$lP7t9X8a9b8c$e8d9c0...', 'ngo', '1234567890');