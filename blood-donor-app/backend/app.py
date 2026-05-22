from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import sqlite3
import os
import random
import string
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(
    __name__,
    template_folder='../mobile_app/templates',
    static_folder='../mobile_app/static'
)

app.secret_key = 'blood-notify-secret-2026'
CORS(app, origins=['http://127.0.0.1:5000', 'http://localhost:5000'])

# Fast2SMS API Key
FAST2SMS_API_KEY = '7zHf5RckuJGFedqtrmb2PxC3K0aDipysjYw8ThoE1VOSAI4NnLBHOeXs3vFT64Wo1qDJtg9xLSMGC0lk'

# Gmail SMTP Config for sending email notifications
# To use: enable 2-Step Verification on your Google account, then create an App Password
# at https://myaccount.google.com/apppasswords
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', '')  # e.g. yourname@gmail.com
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')  # Gmail App Password
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

# DATABASE

db_path = os.path.join(os.path.dirname(__file__), 'blood.db')
connection = sqlite3.connect(
    db_path,
    check_same_thread=False
)

cursor = connection.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT DEFAULT 'admin'
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS donors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    phone TEXT,
    email TEXT UNIQUE,
    password TEXT,
    blood_group TEXT,
    address TEXT,
    city TEXT,
    latitude REAL,
    longitude REAL,
    token TEXT UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    city TEXT,
    latitude REAL,
    longitude REAL,
    token TEXT UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS blood_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT,
    blood_group TEXT,
    city TEXT,
    hospital TEXT,
    details TEXT,
    latitude REAL,
    longitude REAL,
    urgent INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER,
    amount_ml INTEGER,
    date TEXT,
    blood_group TEXT,
    city TEXT,
    notes TEXT,
    FOREIGN KEY(donor_id) REFERENCES donors(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS sms_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER,
    request_id INTEGER,
    message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(donor_id) REFERENCES donors(id),
    FOREIGN KEY(request_id) REFERENCES blood_requests(id)
)
''')

def ensure_column(table, column_name, definition):
    cursor.execute(f'PRAGMA table_info({table})')
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN {definition}')
        connection.commit()

ensure_column('users', 'role', 'role TEXT DEFAULT "admin"')
ensure_column('donors', 'email', 'email TEXT')
ensure_column('donors', 'password', 'password TEXT')
ensure_column('donors', 'latitude', 'latitude REAL')
ensure_column('donors', 'longitude', 'longitude REAL')
ensure_column('donors', 'token', 'token TEXT')
ensure_column('blood_requests', 'latitude', 'latitude REAL')
ensure_column('blood_requests', 'longitude', 'longitude REAL')
ensure_column('blood_requests', 'token', 'token TEXT')
ensure_column('patients', 'token', 'token TEXT')

ensure_column('donations', 'age', 'age INTEGER')
ensure_column('donations', 'sex', 'sex TEXT')
ensure_column('donations', 'bp', 'bp TEXT')
ensure_column('donations', 'sugar', 'sugar TEXT')
ensure_column('donations', 'medical_condition', 'medical_condition TEXT')

ensure_column('blood_requests', 'age', 'age INTEGER')
ensure_column('blood_requests', 'sex', 'sex TEXT')

# BACKFILL MIGRATION: existing rows may have NULL token/lat/lng
def generate_token(prefix='D', length=6):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{suffix}"


def geocode_location(address):
    if not address or address.strip() == '':
        return None, None

    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': address,
                'format': 'json',
                'limit': 1
            },
            headers={
                'User-Agent': 'BloodRescueApp/2026'
            },
            timeout=8
        )
        data = response.json()
        if isinstance(data, list) and data:
            return float(data[0].get('lat')), float(data[0].get('lon'))
    except Exception:
        pass
    return None, None


def backfill_donors():
    try:
        # 1) Backfill tokens where missing (fast)
        cursor.execute('SELECT id FROM donors WHERE token IS NULL OR token = ""')
        donor_ids = [row[0] for row in cursor.fetchall()]
        for donor_id in donor_ids:
            token = generate_token('D')
            cursor.execute('SELECT id FROM donors WHERE token=?', (token,))
            if cursor.fetchone():
                token = generate_token('D')
            cursor.execute('UPDATE donors SET token=? WHERE id=?', (token, donor_id))

        # 2) Backfill geocodes where missing (bounded + resilient so server startup doesn't hang)
        cursor.execute(
            'SELECT id, address, city FROM donors WHERE (latitude IS NULL OR longitude IS NULL) AND address IS NOT NULL AND city IS NOT NULL LIMIT 10'
        )
        rows = cursor.fetchall()
        for donor_id, address, city in rows:
            try:
                addr = f"{(address or '').strip()}, {(city or '').strip()}".strip(' ,')
                lat, lon = geocode_location(addr)
                if lat is not None and lon is not None:
                    cursor.execute(
                        'UPDATE donors SET latitude=?, longitude=? WHERE id=?',
                        (lat, lon, donor_id)
                    )
            except Exception as row_error:
                # never block startup because of one failing geocode row
                print('Geocode backfill failed for donor', donor_id, row_error)

        connection.commit()
    except Exception as e:
        print('Backfill donors migration failed:', e)

cursor.execute(
    '''
    INSERT OR IGNORE INTO users (username, password, role)
    VALUES ('admin', 'admin', 'admin')
    '''
)

backfill_donors()

connection.commit()

# AUTH

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    cursor.execute(
        'SELECT id, role FROM users WHERE username=? AND password=?',
        (username, password)
    )
    user = cursor.fetchone()

    if user:
        session['logged_in'] = True
        session['username'] = username
        session['role'] = user[1] or 'admin'
        return redirect(url_for('home'))

    cursor.execute(
        'SELECT id, name FROM donors WHERE email=? AND password=?',
        (username, password)
    )
    donor = cursor.fetchone()

    if donor:
        session['logged_in'] = True
        session['username'] = donor[1]
        session['role'] = 'donor'
        session['donor_id'] = donor[0]
        return redirect(url_for('user_dashboard'))

    return render_template('login.html', error='Login failed. Use admin/admin or donor credentials.')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'GET':
        return render_template('patient_login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    cursor.execute(
        'SELECT id, name FROM patients WHERE email=? AND password=?',
        (email, password)
    )
    patient = cursor.fetchone()
    if patient:
        session.clear()
        session['logged_in'] = True
        session['role'] = 'patient'
        session['patient_id'] = patient[0]
        session['username'] = patient[1]
        return redirect(url_for('patient_dashboard'))

    return render_template('patient_login.html', login_error='Invalid patient credentials. Register below if you are new.')

@app.route('/patient-signup', methods=['POST'])
def patient_signup():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    city = request.form.get('city', '').strip()

    if not name or not email or not password:
        return render_template('patient_login.html', signup_error='Please provide name, email, password, and city.')

    try:
        token = generate_token('P')
        cursor.execute(
            '''
            INSERT INTO patients (name, email, password, city, token)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (name, email, password, city, token)
        )
        connection.commit()
        return render_template('patient_login.html', signup_success='Patient account created successfully. Please log in.')
    except Exception as error:
        err_str = str(error).lower()
        if 'unique constraint' in err_str or 'unique' in err_str:
            friendly = 'An account with this email already exists. Please log in instead.'
        else:
            friendly = 'Registration failed. Please try again later.'
        return render_template('patient_login.html', signup_error=friendly)

# PAGES

@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'donor':
        return redirect(url_for('user_dashboard'))
    return render_template('index.html')

@app.route('/donate')
def donate_page():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('donate.html')

@app.route('/blood-needed')
def blood_needed_page():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('blood-needed.html')

@app.route('/urgent-blood')
def urgent_blood_page():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('urgent-blood.html')

@app.route('/user-dashboard')
def user_dashboard():
    if not session.get('logged_in') or session.get('role') != 'donor':
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

@app.route('/patient-dashboard')
def patient_dashboard():
    if not session.get('logged_in') or session.get('role') != 'patient':
        return redirect(url_for('patient-login'))
    return render_template('patient_dashboard.html')

# API

@app.route('/api/register-donor', methods=['POST'])
def api_register_donor():
    data = request.get_json()
    try:
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude is None or longitude is None:
            latitude, longitude = geocode_location(f"{data.get('address', '')}, {data.get('city', '')}")

        token = generate_token('D')
        cursor.execute(
            '''
            INSERT INTO donors
            (name, phone, email, password, blood_group, address, city, latitude, longitude, token)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                data.get('name', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('password', ''),
                data.get('blood_group', ''),
                data.get('address', ''),
                data.get('city', ''),
                latitude,
                longitude,
                token
            )
        )
        connection.commit()
        return jsonify({'success': True, 'message': 'Donor registered successfully'})
    except Exception as error:
        err_str = str(error).lower()
        if 'unique' in err_str:
            msg = 'A donor with this email already exists.'
        else:
            msg = 'Registration failed. Please try again.'
        return jsonify({'success': False, 'message': msg})

@app.route('/api/search-donors')
def api_search_donors():
    blood_group = request.args.get('blood_group', '').strip()
    city = request.args.get('city', '').strip()
    patient_lat = request.args.get('latitude')
    patient_lon = request.args.get('longitude')

    query = '''
        SELECT id, name, phone, email, blood_group, address, city, latitude, longitude, token
        FROM donors
        WHERE 1=1
    '''
    params = []
    if blood_group:
        query += ' AND blood_group = ? COLLATE NOCASE'
        params.append(blood_group)
    if city:
        query += ' AND city LIKE ? COLLATE NOCASE'
        params.append(f'{city}%')
    query += ' ORDER BY name'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    result = []
    for donor in rows:
        donor_data = {
            'id': donor[0],
            'name': donor[1],
            'phone': donor[2],
            'email': donor[3],
            'blood_group': donor[4],
            'address': donor[5],
            'city': donor[6],
            'latitude': donor[7],
            'longitude': donor[8],
            'token': donor[9],
            'distance_km': None
        }
        if patient_lat and patient_lon and donor[7] is not None and donor[8] is not None:
            donor_data['distance_km'] = calculate_distance(
                float(patient_lat),
                float(patient_lon),
                float(donor[7]),
                float(donor[8])
            )
        result.append(donor_data)

    if patient_lat and patient_lon:
        result.sort(key=lambda d: d['distance_km'] if d['distance_km'] is not None else float('inf'))

    return jsonify(result)


@app.route('/api/find-donor')
def api_find_donor():
    """
    Find donor by token (e.g. D-XXXXXX) or by numeric id.
    Query param: key
    """
    key = request.args.get('key', '').strip()
    if not key:
        return jsonify({'success': False, 'message': 'Missing key'}), 400

    if key.isdigit():
        cursor.execute(
            'SELECT id, name, phone, email, blood_group, address, city, latitude, longitude, token FROM donors WHERE id=?',
            (int(key),)
        )
    else:
        token_key = key.upper()
        if '-' not in token_key:
            token_key = f'D-{token_key}'

        cursor.execute(
            'SELECT id, name, phone, email, blood_group, address, city, latitude, longitude, token FROM donors WHERE UPPER(token)=?',
            (token_key,)
        )

    row = cursor.fetchone()
    if not row:
        return jsonify({'success': False, 'message': 'Donor not found', 'donor': None}), 404

    donor = {
        'id': row[0],
        'name': row[1],
        'phone': row[2],
        'email': row[3],
        'blood_group': row[4],
        'address': row[5],
        'city': row[6],
        'latitude': row[7],
        'longitude': row[8],
        'token': row[9]
    }
    return jsonify({'success': True, 'message': 'Donor found', 'donor': donor})


@app.route('/api/add-donation', methods=['POST'])
def api_add_donation():
    data = request.get_json()

    try:
        cursor.execute(
            '''
            INSERT INTO donations
            (donor_id, amount_ml, date, blood_group, city, notes, age, sex, bp, sugar, medical_condition)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                data.get('donor_id'),
                data.get('amount_ml'),
                data.get('date'),
                data.get('blood_group', ''),
                data.get('city', ''),
                data.get('notes', ''),
                data.get('age'),
                data.get('sex', ''),
                data.get('bp', ''),
                data.get('sugar', ''),
                data.get('medical_condition', '')
            )
        )
        connection.commit()
        return jsonify({'success': True, 'message': 'Donation recorded successfully'})
    except Exception as error:
        return jsonify({'success': False, 'message': str(error)})

@app.route('/api/donors')
def api_donors():
    try:
        cursor.execute('SELECT id, name, phone, email, blood_group, address, city, latitude, longitude, token FROM donors ORDER BY name')
        rows = cursor.fetchall()
        result = []
        for donor in rows:
            result.append({
                'id': donor[0],
                'name': donor[1],
                'phone': donor[2],
                'email': donor[3],
                'blood_group': donor[4],
                'address': donor[5],
                'city': donor[6],
                'latitude': donor[7],
                'longitude': donor[8],
                'token': donor[9]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/donor-details/<int:donor_id>')
def api_donor_details(donor_id):
    """Get donor info + their latest donation medical details."""
    try:
        cursor.execute(
            'SELECT id, name, phone, email, blood_group, address, city, latitude, longitude, token FROM donors WHERE id=?',
            (donor_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Donor not found'}), 404

        donor = {
            'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
            'blood_group': row[4], 'address': row[5], 'city': row[6],
            'latitude': row[7], 'longitude': row[8], 'token': row[9]
        }

        # Get latest donation with medical info
        cursor.execute(
            '''
            SELECT amount_ml, date, blood_group, city, notes, age, sex, bp, sugar, medical_condition
            FROM donations WHERE donor_id=? ORDER BY date DESC LIMIT 1
            ''',
            (donor_id,)
        )
        donation_row = cursor.fetchone()
        if donation_row:
            donor['last_donation'] = {
                'amount_ml': donation_row[0],
                'date': donation_row[1],
                'blood_group': donation_row[2],
                'city': donation_row[3],
                'notes': donation_row[4],
                'age': donation_row[5],
                'sex': donation_row[6],
                'bp': donation_row[7],
                'sugar': donation_row[8],
                'medical_condition': donation_row[9]
            }
        else:
            donor['last_donation'] = None

        return jsonify({'success': True, 'donor': donor})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/donations')
def api_donations():
    try:
        cursor.execute(
            '''
            SELECT d.id, r.name, d.amount_ml, d.date, d.blood_group, d.city, d.notes
            FROM donations d
            LEFT JOIN donors r ON r.id = d.donor_id
            ORDER BY d.date DESC
            '''
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'donor_name': row[1] or 'Unknown',
                'amount_ml': row[2],
                'date': row[3],
                'blood_group': row[4],
                'city': row[5],
                'notes': row[6]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/create-request', methods=['POST'])
def api_create_request():
    data = request.get_json()
    try:
        urgent_flag = 1 if data.get('urgent') else 0
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude is None or longitude is None:
            latitude, longitude = geocode_location(f"{data.get('hospital', '')}, {data.get('city', '')}")

        token = generate_token('R')
        cursor.execute(
            '''
            INSERT INTO blood_requests
            (patient_name, blood_group, city, hospital, details, latitude, longitude, urgent, token, age, sex)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                data.get('patient_name', ''),
                data.get('blood_group', ''),
                data.get('city', ''),
                data.get('hospital', ''),
                data.get('details', ''),
                latitude,
                longitude,
                urgent_flag,
                token,
                data.get('age'),
                data.get('sex', '')
            )
        )
        request_id = cursor.lastrowid
        connection.commit()

        notified_donors = []
        if urgent_flag:
            notified_donors = notify_nearest_donors(data.get('blood_group', ''), data.get('city', ''), request_id, data.get('patient_name', ''))

        return jsonify({'success': True, 'message': 'Blood request created successfully', 'urgent': bool(urgent_flag), 'notified_donors': notified_donors})
    except Exception as error:
        return jsonify({'success': False, 'message': str(error)})

@app.route('/api/requests')
def api_requests():
    try:
        cursor.execute(
            '''
            SELECT id, patient_name, blood_group, city, hospital, details, latitude, longitude, urgent, created_at, token
            FROM blood_requests
            WHERE urgent=0
            ORDER BY created_at DESC
            '''
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'patient_name': row[1],
                'blood_group': row[2],
                'city': row[3],
                'hospital': row[4],
                'details': row[5],
                'latitude': row[6],
                'longitude': row[7],
                'urgent': bool(row[8]),
                'created_at': row[9],
                'token': row[10]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/urgent-requests')
def api_urgent_requests():
    try:
        cursor.execute(
            '''
            SELECT id, patient_name, blood_group, city, hospital, details, latitude, longitude, urgent, created_at, token
            FROM blood_requests
            WHERE urgent=1
            ORDER BY created_at DESC
            '''
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'patient_name': row[1],
                'blood_group': row[2],
                'city': row[3],
                'hospital': row[4],
                'details': row[5],
                'latitude': row[6],
                'longitude': row[7],
                'urgent': bool(row[8]),
                'created_at': row[9],
                'token': row[10]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sms-log')
def api_sms_log():
    try:
        cursor.execute(
            '''
            SELECT s.id, d.name, d.phone, b.patient_name, s.message, s.sent_at
            FROM sms_log s
            LEFT JOIN donors d ON d.id = s.donor_id
            LEFT JOIN blood_requests b ON b.id = s.request_id
            ORDER BY s.sent_at DESC
            '''
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'donor_name': row[1],
                'donor_phone': row[2],
                'patient_name': row[3],
                'message': row[4],
                'sent_at': row[5]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patient-blood-request', methods=['POST'])
def api_patient_blood_request():
    data = request.get_json()
    try:
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude is None or longitude is None:
            latitude, longitude = geocode_location(f"{data.get('hospital', '')}, {data.get('city', '')}")

        token = generate_token('R')
        cursor.execute(
            '''
            INSERT INTO blood_requests
            (patient_name, blood_group, city, hospital, details, latitude, longitude, urgent, token, age, sex)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                data.get('patient_name', ''),
                data.get('blood_group', ''),
                data.get('city', ''),
                data.get('hospital', ''),
                data.get('details', ''),
                latitude,
                longitude,
                1,
                token,
                data.get('age'),
                data.get('sex', '')
            )
        )
        request_id = cursor.lastrowid
        connection.commit()
        notified_donors = notify_nearest_donors(data.get('blood_group', ''), data.get('city', ''), request_id, data.get('patient_name', ''))
        return jsonify({'success': True, 'message': 'Blood request created successfully', 'token': token, 'notified_donors': notified_donors})
    except Exception as error:
        return jsonify({'success': False, 'message': str(error)})

@app.route('/api/stats')
def api_stats():
    try:
        cursor.execute('SELECT COUNT(*) FROM donors')
        donors_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM donations')
        donations_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM blood_requests WHERE urgent=1')
        urgent_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM blood_requests WHERE urgent=0')
        requests_count = cursor.fetchone()[0]
        return jsonify({
            'donors': donors_count,
            'donations': donations_count,
            'urgent_requests': urgent_count,
            'requests': requests_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patient-history')
def api_patient_history():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    patient_name = session.get('username')
    try:
        cursor.execute(
            '''
            SELECT id, patient_name, blood_group, city, hospital, created_at, token
            FROM blood_requests
            WHERE patient_name = ?
            ORDER BY created_at DESC
            ''',
            (patient_name,)
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0],
                'patient_name': row[1],
                'blood_group': row[2],
                'city': row[3],
                'hospital': row[4],
                'created_at': row[5],
                'token': row[6]
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helpers

def calculate_distance(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    if None in (lat1, lon1, lat2, lon2):
        return None
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 6371 * c


def generate_token(prefix='D', length=6):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{suffix}"


def notify_nearest_donors(blood_group, city, request_id, patient_name):
    print(f"\n=== URGENT REQUEST ALERT ===")
    print(f"Patient: {patient_name}, Blood: {blood_group}, City: {city}")

    cursor.execute('SELECT latitude, longitude FROM blood_requests WHERE id=?', (request_id,))
    request_geo = cursor.fetchone()
    request_lat = request_geo[0] if request_geo else None
    request_lon = request_geo[1] if request_geo else None

    cursor.execute(
        'SELECT id, name, phone, email, latitude, longitude FROM donors WHERE blood_group=? COLLATE NOCASE AND city=? COLLATE NOCASE',
        (blood_group, city)
    )
    donors = cursor.fetchall()

    if not donors:
        print(f"No donors in {city}, searching by blood group...")
        cursor.execute(
            'SELECT id, name, phone, email, latitude, longitude FROM donors WHERE blood_group=? COLLATE NOCASE',
            (blood_group,)
        )
        donors = cursor.fetchall()

    donor_entries = []
    for donor in donors:
        # donor fields: id, name, phone, email, latitude, longitude
        lat, lon = donor[4], donor[5]
        distance = calculate_distance(request_lat, request_lon, lat, lon) if request_lat is not None and request_lon is not None else None
        donor_entries.append((distance if distance is not None else float('inf'), donor))

    donor_entries.sort(key=lambda entry: entry[0])
    donors_sorted = [entry[1] for entry in donor_entries]
    
    notified = []
    for distance, donor in donor_entries:
        notified.append({
            'id': donor[0],
            'name': donor[1],
            'phone': donor[2],
            'email': donor[3],
            'latitude': donor[4],
            'longitude': donor[5],
            'distance_km': round(distance, 2) if distance != float('inf') else None
        })

    print(f"Found {len(donors_sorted)} matching donor(s)")

    message = f"Urgent blood needed for {patient_name}. Blood group {blood_group} required in {city}. Please respond immediately."

    for donor in donors_sorted:
        cursor.execute(
            '''
            INSERT INTO sms_log (donor_id, request_id, message)
            VALUES (?, ?, ?)
            ''',
            (donor[0], request_id, message)
        )
        print(f"\n>>> Sending SMS to {donor[1]} ({donor[2]})...")
        
        try:
            response = requests.post(
                'https://www.fast2sms.com/dev/bulkV2',
                headers={
                    'authorization': FAST2SMS_API_KEY,
                    'Content-Type': 'application/json'
                },
                json={
                    'route': 'q',
                    'message': message,
                    'language': 'english',
                    'flash': 0,
                    'numbers': donor[2]
                },
                timeout=10
            )
            result = response.json()
            print(f"API Response: {result}")
            
            if result.get('return'):
                print(f"[OK] SMS SUCCESSFULLY SENT to {donor[1]}")
            else:
                print(f"[FAILED] SMS FAILED: {result.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"[FAILED] ERROR: {str(e)}")
            
        # Send Email Notification
        donor_email = donor[3]
        if donor_email:
            print(f">>> Sending Email to {donor[1]} ({donor_email})...")
            try:
                msg = MIMEMultipart()
                sender_email = SMTP_EMAIL or 'noreply@bloodrescue.app'
                msg['From'] = sender_email
                msg['To'] = donor_email
                msg['Subject'] = f"URGENT: Blood Group {blood_group} Needed in {city}"
                
                body = f"""Hello {donor[1]},

An urgent blood request has been made.
Patient Name: {patient_name}
Blood Group: {blood_group}
City: {city}

Please respond immediately to save a life.

Thank you,
Blood Rescue Team"""
                msg.attach(MIMEText(body, 'plain'))
                
                if SMTP_EMAIL and SMTP_PASSWORD:
                    # Use Gmail SMTP with TLS
                    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
                    server.starttls()
                    server.login(SMTP_EMAIL, SMTP_PASSWORD)
                    server.send_message(msg)
                    server.quit()
                    print(f"[OK] EMAIL SENT to {donor_email}")
                else:
                    print(f"[SKIP] EMAIL not configured. Set SMTP_EMAIL and SMTP_PASSWORD env vars. (Would send to {donor_email})")
            except Exception as e:
                print(f"[FAILED] EMAIL ERROR: {str(e)}")

    connection.commit()
    print(f"=== END ALERT ===\n")
    return notified


def geocode_location(address):
    if not address or address.strip() == '':
        return None, None

    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': address,
                'format': 'json',
                'limit': 1
            },
            headers={
                'User-Agent': 'BloodRescueApp/2026'
            },
            timeout=8
        )
        data = response.json()
        if isinstance(data, list) and data:
            return float(data[0].get('lat')), float(data[0].get('lon'))
    except Exception:
        pass
    return None, None

if __name__ == '__main__':
    app.run(debug=True)
