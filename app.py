from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
import re
import random
import time
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json

app = Flask(__name__)
CORS(app)

# Rate Limiting - IP बैन से बचने के लिए
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["50 per minute", "500 per hour"]
)

# ============ CONFIGURATION ============
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Simple Cache (5 मिनट के लिए)
cache = {}
CACHE_DURATION = 300  # 5 minutes

def get_cache_key(service, query):
    return f"{service}:{query.lower().strip()}"

def get_from_cache(key):
    if key in cache:
        data, timestamp = cache[key]
        if datetime.now() - timestamp < timedelta(seconds=CACHE_DURATION):
            return data
        else:
            del cache[key]
    return None

def set_cache(key, data):
    cache[key] = (data, datetime.now())

# ============ VEHICLE INFO (FIXED) ============
def get_vehicle_details(rc):
    try:
        rc = rc.strip().upper().replace(' ', '').replace('-', '').replace('=', '')
        
        # Cache check
        cache_key = get_cache_key('vehicle', rc)
        cached = get_from_cache(cache_key)
        if cached:
            return cached
        
        # Try multiple sources
        sources = [
            f"https://vahanx.in/rc-search/{rc}",
            f"https://www.vahan.nic.in/nrservices/faces/RC/RCStatus.xhtml"  # Backup
        ]
        
        for url in sources:
            try:
                resp = requests.get(
                    url, 
                    headers={
                        "User-Agent": random.choice(USER_AGENTS),
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    timeout=15
                )
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    data = extract_vehicle_data(soup, rc)
                    if data and len(data) > 2:
                        data["Source"] = url
                        data["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        set_cache(cache_key, data)
                        return data
            except:
                continue
        
        # अगर कुछ नहीं मिला
        return {
            "status": "Not Found",
            "message": "Vehicle details not found. Please check the RC number.",
            "Registration Number": rc,
            "suggestion": "Try different formats: DL8CX1234, MH12DE4321"
        }
        
    except Exception as e:
        return {"status": "Error", "message": str(e)}

def extract_vehicle_data(soup, rc):
    data = {"Registration Number": rc}
    
    # Multiple extraction patterns
    patterns = [
        # Pattern 1: Standard table rows
        ('table', 'tr', ['td', 'th']),
        # Pattern 2: div with specific classes
        ('div', {'class': re.compile(r'(detail|info|data|row)')}, ['span', 'p']),
        # Pattern 3: Direct span-p pairs
        ('span', None, ['p', 'div'])
    ]
    
    for tag, attrs, child_tags in patterns:
        try:
            if attrs:
                elements = soup.find_all(tag, attrs)
            else:
                elements = soup.find_all(tag)
            
            for elem in elements:
                if child_tags:
                    for child_tag in child_tags:
                        child = elem.find(child_tag) if isinstance(child_tag, str) else elem.find(*child_tag)
                        if child:
                            label = elem.get_text(strip=True)
                            value = child.get_text(strip=True)
                            if label and value and len(label) > 2 and len(value) > 1:
                                # Clean up label
                                label = re.sub(r'[:*\-]', '', label).strip()
                                if len(label) < 50:  # Avoid garbage
                                    data[label] = value
        except:
            continue
    
    # अगर डेटा बहुत कम है, तो और गहराई से खोजें
    if len(data) < 3:
        # Find all text patterns
        text = soup.get_text()
        important_fields = ['Owner', 'Name', 'Address', 'Model', 'Maker', 'Fuel', 'Engine', 'Chassis', 'RTO']
        for field in important_fields:
            pattern = re.compile(f'{field}.*?:.*?([^\\n]{{5,50}})', re.I)
            matches = pattern.findall(text)
            if matches:
                data[field] = matches[0].strip()
    
    return data

# ============ PHONE INFO (FIXED - Real API) ============
def get_phone_details(number):
    try:
        number = re.sub(r'[^0-9+]', '', number).strip()
        if number.startswith('+91'):
            number = number[3:]
        if len(number) != 10:
            return {"status": "Error", "message": "Enter a valid 10-digit Indian number."}
        
        # Cache check
        cache_key = get_cache_key('phone', number)
        cached = get_from_cache(cache_key)
        if cached:
            return cached
        
        # Try numverify API (फ्री)
        try:
            # Note: numverify requires API key - get from https://numverify.com/
            # For demo, we'll use a reliable free API
            url = f"https://api.veriphone.io/v2/verify?phone={number}&default_country=IN"
            # Free tier: 250 requests/day
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    result = {
                        "phone": number,
                        "country": "India",
                        "carrier": data.get('carrier', 'Unknown'),
                        "location": data.get('city', 'Unknown'),
                        "valid": data.get('phone_valid', False),
                        "type": data.get('phone_type', 'Mobile'),
                        "Service": "Phone Info"
                    }
                    set_cache(cache_key, result)
                    return result
        except:
            pass
        
        # Fallback: Local carrier lookup based on prefix
        prefix = number[:2]
        operators = {
            '98': 'Airtel', '99': 'Airtel', '97': 'Airtel', '96': 'Airtel',
            '91': 'Vi', '92': 'Vi', '93': 'Vi', '94': 'Vi',
            '88': 'BSNL', '89': 'BSNL',
            '70': 'Jio', '71': 'Jio', '72': 'Jio', '73': 'Jio',
            '74': 'Jio', '75': 'Jio', '76': 'Jio', '77': 'Jio',
            '78': 'Jio', '79': 'Jio'
        }
        
        # More accurate state mapping
        state_prefixes = {
            '98': 'Maharashtra', '99': 'Karnataka', '97': 'Delhi', '96': 'UP',
            '91': 'Gujarat', '92': 'Rajasthan', '93': 'Bihar', '94': 'Tamil Nadu',
            '88': 'West Bengal', '89': 'Punjab'
        }
        
        result = {
            "phone": number,
            "carrier": operators.get(prefix, "Unknown"),
            "location": state_prefixes.get(prefix, "India"),
            "valid": True,
            "type": "Mobile",
            "Service": "Phone Info (Fallback)",
            "note": "Use numverify.com for more accurate data"
        }
        set_cache(cache_key, result)
        return result
        
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ IFSC INFO (FIXED) ============
def get_ifsc_info(ifsc):
    try:
        ifsc = ifsc.upper().strip()
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
            return {"status": "Error", "message": "Invalid IFSC format. Must be: ABCD0XXXXXX"}
        
        cache_key = get_cache_key('ifsc', ifsc)
        cached = get_from_cache(cache_key)
        if cached:
            return cached
        
        # Try Razorpay API
        url = f"https://ifsc.razorpay.com/{ifsc}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "ifsc": data.get("IFSC"),
                "bank": data.get("BANK"),
                "branch": data.get("BRANCH"),
                "address": data.get("ADDRESS"),
                "city": data.get("CITY"),
                "state": data.get("STATE"),
                "micr": data.get("MICR"),
                "contact": data.get("CONTACT"),
                "Service": "IFSC Info"
            }
            set_cache(cache_key, result)
            return result
        else:
            return {"status": "Error", "message": "IFSC not found"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ IP INFO (FIXED) ============
def get_ip_info(ip):
    try:
        # Validate IP
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            return {"status": "Error", "message": "Invalid IP address format"}
        
        cache_key = get_cache_key('ip', ip)
        cached = get_from_cache(cache_key)
        if cached:
            return cached
        
        # Try ip-api.com
        url = f"http://ip-api.com/json/{ip}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                result = {
                    "ip": ip,
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "timezone": data.get("timezone"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "Service": "IP Info"
                }
                set_cache(cache_key, result)
                return result
        
        return {"status": "Error", "message": "Could not fetch IP info"}
        
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ PINCODE INFO (FIXED) ============
def get_pincode_info(pincode):
    try:
        pincode = str(pincode).strip()
        if not pincode.isdigit() or len(pincode) != 6:
            return {"status": "Error", "message": "Invalid pincode (6 digits required)"}
        
        cache_key = get_cache_key('pincode', pincode)
        cached = get_from_cache(cache_key)
        if cached:
            return cached
        
        url = f"https://api.postalpincode.in/pincode/{pincode}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data and data[0].get('Status') == 'Success':
                post_office = data[0]['PostOffice'][0]
                result = {
                    "pincode": pincode,
                    "city": post_office.get("District"),
                    "state": post_office.get("State"),
                    "district": post_office.get("District"),
                    "post_office": post_office.get("Name"),
                    "delivery_status": post_office.get("DeliveryStatus"),
                    "Service": "Pincode Info"
                }
                set_cache(cache_key, result)
                return result
        
        return {"status": "Error", "message": "Pincode not found"}
        
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ GITHUB INFO (FIXED) ============
def get_github_info(username):
    try:
        username = username.strip()
        if not username:
            return {"status": "Error", "message": "Username required"}
        
        cache_key = get_cache_key('github', username)
        cached = get_from_cache(cache_key)
        if cached:
            return cached
        
        url = f"https://api.github.com/users/{username}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "username": username,
                "name": data.get("name") or username,
                "bio": data.get("bio") or "Not provided",
                "location": data.get("location") or "Unknown",
                "public_repos": data.get("public_repos", 0),
                "followers": data.get("followers", 0),
                "following": data.get("following", 0),
                "created_at": data.get("created_at", "").split('T')[0],
                "url": data.get("html_url"),
                "Service": "GitHub Info"
            }
            set_cache(cache_key, result)
            return result
        else:
            return {"status": "Error", "message": "User not found"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ EMAIL INFO (FIXED) ============
def get_email_info(email):
    try:
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return {"status": "Error", "message": "Invalid email format"}
        
        domain = email.split('@')[1]
        providers = {
            'gmail.com': 'Google (Gmail)',
            'yahoo.com': 'Yahoo',
            'outlook.com': 'Microsoft Outlook',
            'hotmail.com': 'Microsoft Hotmail',
            'rediffmail.com': 'Rediffmail',
            'protonmail.com': 'ProtonMail',
            'zoho.com': 'Zoho Mail',
            'aol.com': 'AOL',
        }
        
        # Check if domain exists
        try:
            import socket
            socket.gethostbyname(domain)
            domain_exists = True
        except:
            domain_exists = False
        
        return {
            "email": email,
            "domain": providers.get(domain, domain),
            "domain_exists": domain_exists,
            "valid_format": True,
            "disposable": domain in ['temp-mail.org', 'guerrillamail.com', '10minutemail.com'],
            "Service": "Email Info"
        }
        
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ DEMO SERVICES (Better format) ============
def demo_service_response(service, identifier):
    return {
        "service": service,
        "identifier": identifier,
        "status": "Demo Data",
        "note": "This is sample data. For production, integrate real API.",
        "data": {
            "name": f"Demo {service.capitalize()} User",
            "id": identifier,
            "valid": "Yes",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    }

# ============ ROUTES ============
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/vehicle/<path:query>')
@limiter.limit("20 per minute")
def vehicle_route(query):
    return jsonify(get_vehicle_details(query))

@app.route('/num/<path:query>')
@limiter.limit("20 per minute")
def num_route(query):
    return jsonify(get_phone_details(query))

@app.route('/truecaller/<path:query>')
@limiter.limit("10 per minute")
def truecaller_route(query):
    return jsonify(demo_service_response("truecaller", query))

@app.route('/aadhar/<path:query>')
@limiter.limit("10 per minute")
def aadhar_route(query):
    return jsonify(demo_service_response("aadhar", query))

@app.route('/pan/<path:query>')
@limiter.limit("10 per minute")
def pan_route(query):
    return jsonify(demo_service_response("pan", query))

@app.route('/ifsc/<path:query>')
@limiter.limit("30 per minute")
def ifsc_route(query):
    return jsonify(get_ifsc_info(query))

@app.route('/ip/<path:query>')
@limiter.limit("30 per minute")
def ip_route(query):
    return jsonify(get_ip_info(query))

@app.route('/email/<path:query>')
@limiter.limit("30 per minute")
def email_route(query):
    return jsonify(get_email_info(query))

@app.route('/pincode/<path:query>')
@limiter.limit("30 per minute")
def pincode_route(query):
    return jsonify(get_pincode_info(query))

@app.route('/github/<path:query>')
@limiter.limit("20 per minute")
def github_route(query):
    return jsonify(get_github_info(query))

# Demo services
@app.route('/ff/<path:query>')
def ff_route(query):
    return jsonify(demo_service_response("freefire", query))

@app.route('/numvl/<path:query>')
def numvl_route(query):
    return jsonify(demo_service_response("numvl", query))

@app.route('/family/<path:query>')
def family_route(query):
    return jsonify(demo_service_response("family", query))

@app.route('/insta/<path:query>')
def insta_route(query):
    return jsonify(demo_service_response("instagram", query))

@app.route('/tg/<path:query>')
def tg_route(query):
    return jsonify(demo_service_response("telegram", query))

@app.route('/pak/<path:query>')
def pak_route(query):
    return jsonify(demo_service_response("pakistan", query))

@app.route('/bgmi/<path:query>')
def bgmi_route(query):
    return jsonify(demo_service_response("bgmi", query))

@app.route('/ping')
def ping():
    return jsonify({
        "status": "alive",
        "services": 17,
        "cache_size": len(cache),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ============ ERROR HANDLERS ============
@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "Error", "message": "Service not found"}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "status": "Error", 
        "message": "Rate limit exceeded. Please wait a moment.",
        "retry_after": "60 seconds"
    }), 429

@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "Error", "message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)
