# 🍲 FoodBridge

[![Live Demo](https://img.shields.io/badge/Live%20Demo-foodbridge--dev.onrender.com-1B4332?style=for-the-badge)](https://foodbridge-dev.onrender.com/)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat&logo=flask&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-7952B3?style=flat&logo=bootstrap&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat&logo=postgresql&logoColor=white)
![Deployment](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=flat&logo=render&logoColor=white)

**Zero Hunger. Zero Waste.**

FoodBridge connects surplus food from local restaurants, caterers, and businesses to NGOs and shelters that need it — in real time. A donor lists what's available and when it needs to be picked up; nearby NGOs claim it, coordinate logistics in-app, and get notified the moment something new goes live.

**Live Demo:** [foodbridge-dev.onrender.com](https://foodbridge-dev.onrender.com/)

---

## 🔑 Try It Live

The app is deployed on Render's free tier, so the first load after a period of inactivity can take **30–60 seconds** to spin back up — that's the server waking up, not a bug.

Two test accounts are seeded so you can try both sides of the marketplace without registering:

| Role | Username | Password |
|---|---|---|
| Donor | `testdonor` | `123456` |
| NGO | `testngo` | `123456` |

Log in as the donor to post a listing, then log in as the NGO in another tab (or after logging out) to claim it and try the in-app chat.

---

## ✨ Key Features

- **Two dedicated roles** — Donors (restaurants/caterers) and NGOs (shelters/community centers) each get their own dashboard and workflow from registration onward.
- **Structured donation listings** — food item, category, quantity + unit, packaging type, pickup address, and an optional GPS pin (via the browser's Geolocation API) that NGOs can open directly in Google Maps.
- **Smart split-claiming** — an NGO can claim a full listing or just part of it. Partial claims automatically spin off a new "Active" listing for the remaining quantity, so nothing sits unclaimed unnecessarily.
- **Flatpickr pickup deadlines** — donors set an expiry via a date/time picker with one-click presets (+2h / +4h / +6h / end of day); past dates are blocked.
- **Live countdown timers** — each listing on the NGO feed counts down to its pickup deadline client-side and flags itself once expired.
- **Instant client-side search** — the NGO feed filters by food item or organization name as you type, no reload.
- **In-app chat** — once a listing is claimed, donor and NGO get a dedicated per-donation chat thread to coordinate pickup.
- **Notifications** — a bell icon polls for unread alerts every 5 seconds and shows new donations, claims, and chat messages, with a dropdown preview and a full inbox page.
- **Profiles & trust badges** — users set a default pickup/HQ address, a description/bio, and a contact number; a `Verified` / `Pending Verification` badge is shown on the profile.

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python, Flask, Werkzeug (password hashing), Gunicorn (production server) |
| **Database** | Dual-mode: PostgreSQL (`psycopg2`) when a `DATABASE_URL` env var is present, otherwise falls back to local SQLite (`foodbridge.db`) |
| **Frontend** | Jinja2 templates, Bootstrap 5 |
| **Fonts** | Fraunces (display/brand) + Public Sans (UI body), loaded via Google Fonts |
| **Interactivity** | Vanilla JS — Flatpickr for date/time selection, HTML5 Geolocation, live countdown timers, notification polling |

> **Note:** `static/style.css` and `static/scipt.js` are legacy files from an earlier design pass — the templates currently in use style everything inline inside `base.html` and don't link to either file. Worth deleting or reconnecting them so the codebase doesn't carry dead weight.

---

## 📂 Project Structure

```
FoodBridge/
├── app.py                  # Flask app: routing, auth, donations, claims, chat, notifications
├── schema.sql               # Table definitions + safe ALTER TABLE migrations + demo seed rows
├── requirements.txt          # Python dependencies
├── foodbridge.db             # Local SQLite database (auto-created on first run)
├── static/
│   ├── style.css              # Legacy stylesheet (currently unused — see note above)
│   └── scipt.js                # Legacy script (currently unused — see note above)
└── templates/
    ├── base.html               # Layout, sticky navbar, notification bell, flash messages
    ├── index.html               # Landing page
    ├── login.html                # Login form
    ├── register.html              # Registration + role selection (donor / NGO)
    ├── donor.html                  # Post a donation, view active listings & claim history
    ├── ngo.html                     # Live donation feed, search, claim flow, "my claims" panel
    ├── profile.html                  # Editable profile: phone, address, description
    ├── chat.html                      # Per-donation messaging thread
    └── notifications.html              # Full notification inbox
```

---

## 🗄️ Database Schema

Four tables, defined in `schema.sql` and auto-created on app startup:

- **`users`** — `username`, hashed `password`, `role` (`donor` / `ngo`), `phone`, plus `default_address`, `description`, and `is_verified`, added via safe `ALTER TABLE ... IF NOT EXISTS` migrations.
- **`donations`** — food details, `quantity`/`unit`, `packaging_note`, `address`, optional `latitude`/`longitude`, `expiry_datetime`, `status` (`Active` / `Claimed`), and `claimed_by`.
- **`notifications`** — per-user alerts (`new_donation`, `claim`, `chat`) with an `is_read` flag.
- **`messages`** — chat messages tied to a `donation_id` and `sender_id`.

---

## 🚀 Local Development Setup

### 1. Clone the repository
```bash
git clone https://github.com/YourUsername/FoodBridge.git
cd FoodBridge
```

### 2. Set up a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
No manual database setup needed — `init_db()` runs automatically on startup and creates `foodbridge.db` with the schema (and two demo accounts) the first time you launch it.
```bash
python app.py
```
The app runs at `http://127.0.0.1:5000/`.

> If you ever need to force a re-init (e.g. after editing `schema.sql`), visit `/init-db-now` while the app is running.

---

## 🌍 Production Deployment (Render)

1. Connect your GitHub repository to a Render Web Service.
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `gunicorn app:app`
4. **Environment variable:** add your PostgreSQL connection string as `DATABASE_URL`. The app detects it automatically and switches from SQLite to PostgreSQL — no code changes needed.

> **Before deploying for real:** `app.secret_key` is currently a hardcoded placeholder (`'final_demo_key_xyz'`) in `app.py`. Swap it for a securely generated secret pulled from an environment variable before this goes anywhere near production.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome — feel free to open an issue if you'd like to help improve FoodBridge.

## 📄 License

© 2026 FoodBridge. Reducing food waste, feeding communities.
