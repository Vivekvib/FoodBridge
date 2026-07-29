CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    phone VARCHAR(20)
);

CREATE TABLE donations (
    id SERIAL PRIMARY KEY,
    donor_id INTEGER NOT NULL,
    org_name VARCHAR(100) NOT NULL,
    food_item VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'Cooked Veg',
    quantity INTEGER NOT NULL,
    unit VARCHAR(30) NOT NULL DEFAULT 'Servings',
    packaging_note VARCHAR(100) DEFAULT 'Not specified',
    address TEXT NOT NULL,
    latitude DOUBLE PRECISION NULL,
    longitude DOUBLE PRECISION NULL,
    expiry_datetime TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    claimed_by INTEGER NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    related_id INTEGER,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    donation_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donation_id) REFERENCES donations (id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE
);

-- DUMMY DATA
INSERT INTO users (username, password, role, phone) VALUES 
('demodonor', 'scrypt:32768:8:1$lP7t9X8a9b8c$e8d9c0...', 'donor', '9876543210'),
('demongo', 'scrypt:32768:8:1$lP7t9X8a9b8c$e8d9c0...', 'ngo', '1234567890');