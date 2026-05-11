# Blood Donor App

This repository contains a simple blood donor mobile app scaffold with a Kivy-based frontend and a Flask backend.

## Structure

- `mobile_app/`
  - `main.py` - entry point for the Kivy application
  - `donor_screen.py` - donor dashboard screen
  - `login_screen.py` - login screen logic
  - `register_screen.py` - registration screen logic
  - `kv/` - Kivy layout files
    - `home.kv`
    - `login.kv`
    - `donor.kv`

- `backend/`
  - `app.py` - Flask backend application
  - `database.py` - SQLite helpers and schema initialization
  - `requirements.txt` - backend dependencies

## Usage

1. Install backend dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

2. Run the backend:
   ```bash
   python backend/app.py
   ```

3. Run the mobile app:
   ```bash
   python mobile_app/main.py
   ```
