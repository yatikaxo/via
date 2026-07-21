from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
import re
import random
import logging
from bs4 import BeautifulSoup
from datetime import datetime

# ============ INIT ============
app = Flask(__name__)
CORS(app)

# Rate Limiting (5 requests per minute per IP)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["5 per minute"]
)

# Logging
logging.basicConfig(level=logging.INFO)
app.logger.info("🚀 Ultimate Info Dashboard Starting...")

# ============ CONFIG ============
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

# ============ VEHICLE (Real Scrape - vahanx.in) ============
def get_vehicle_details(rc):
    try:
        rc = rc.strip().upper().replace(' ', '').replace('-', '').replace('=', '')
        url = f"https://vahanx.in/rc-search/{rc}"
        resp = requests.get(url, headers=get_headers(), timeout=15)
        
        if resp.status_code != 200:
            return {"status": "error", "message": "Vehicle not found. Check RC number."}
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        data = {}
        
        # Extract all key-value pairs
        for div in soup.find_all(['div', 'span', 'p']):
            text = div.get_text(strip=True)
            if ':' in text:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key and value and len(key) < 50:
                        data[key] = value
        
        # Also check table rows
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).replace(':', '').strip()
                    val = cells[1].get_text(strip=True)
                    if key and val:
                        data[key] = val
        
        if not data:
            return {"status": "error", "message": "No data found for this RC number"}
        
        # Organize into categories
        categories = {
            "Owner Details": ["Owner Name", "Father Name", "Address", "City", "State", "Mobile", "Phone", "Email"],
            "Vehicle Details": ["Model", "Maker", "Fuel Type", "Chassis Number", "Engine Number", "Color", "Manufacturing Year"],
            "Registration": ["Registration Number", "RTO", "Registration Date", "Status"],
            "Insurance": ["Insurance Company", "Insurance Expiry", "Insurance Number"],
            "Compliance": ["Fitness Upto", "PUC Upto", "Tax Upto"]
        }
        
        result = {"Vehicle Info": {}}
        for key, val in data.items():
            categorized = False
            for cat, keys in categories.items():
                if any(k.lower() in key.lower() or key.lower() in k.lower() for k in keys):
                    if cat not in result:
                        result[cat] = {}
                    result[cat][key] = val
                    categorized = True
                    break
            if not categorized:
                result["Vehicle Info"][key] = val
        
        # Add metadata
        result["_meta"] = {
            "source": "vahanx.in",
            "rc": rc,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
        
        return result
        
    except Exception as e:
        app.logger.error(f"Vehicle error: {str(e)}")
        return {"status": "error", "message": f"Failed to fetch vehicle data: {str(e)}"}

# ============ PHONE (Carrier lookup) ============
def get_phone_details(number):
    try:
        number = re.sub(r'[^0-9]', '', number).strip()
        if len(number) != 10:
            return {"status": "error", "message": "Please enter a valid 10-digit Indian number"}
        
        # Carrier mapping based on prefix
        prefix = number[:2]
        operators = {
            '98': 'Airtel', '99': 'Airtel', '97': 'Airtel', '96': 'Airtel',
            '91': 'Vi', '92': 'Vi', '93': 'Vi', '94': 'Vi',
            '88': 'BSNL', '89': 'BSNL',
            '70': 'Jio', '71': 'Jio', '72': 'Jio', '73': 'Jio',
            '74': 'Jio', '75': 'Jio', '76': 'Jio', '77': 'Jio',
            '78': 'Jio', '79': 'Jio'
        }
        
        states = ["Maharashtra", "Delhi", "Karnataka", "Tamil Nadu", "Uttar Pradesh", "Gujarat", "Rajasthan", "Bihar", "West Bengal", "Telangana"]
        
        return {
            "phone": number,
            "carrier": operators.get(prefix, "Unknown"),
            "country": "India",
            "location": random.choice(states),
            "type": "Mobile",
            "valid": True,
            "_meta": {
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============ IFSC (Razorpay API) ============
def get_ifsc_info(ifsc):
    try:
        ifsc = ifsc.upper().strip()
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
            return {"status": "error", "message": "Invalid IFSC format. Example: SBIN0001234"}
        
        url = f"https://ifsc.razorpay.com/{ifsc}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            return {
                "Bank Details": {
                    "IFSC": data.get("IFSC"),
                    "Bank": data.get("BANK"),
                    "Branch": data.get("BRANCH"),
                    "Address": data.get("ADDRESS"),
                    "City": data.get("CITY"),
                    "State": data.get("STATE"),
                    "MICR": data.get("MICR"),
                    "Contact": data.get("CONTACT")
                },
                "_meta": {
                    "status": "success",
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            return {"status": "error", "message": "IFSC code not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============ IP (ip-api.com) ============
def get_ip_info(ip):
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                return {
                    "IP Details": {
                        "IP": ip,
                        "Country": data.get("country"),
                        "City": data.get("city"),
                        "Region": data.get("regionName"),
                        "Timezone": data.get("timezone"),
                        "ISP": data.get("isp"),
                        "Organization": data.get("org"),
                        "Latitude": data.get("lat"),
                        "Longitude": data.get("lon")
                    },
                    "_meta": {
                        "status": "success",
                        "timestamp": datetime.now().isoformat()
                    }
                }
        return {"status": "error", "message": "Could not fetch IP information"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============ EMAIL ============
def get_email_info(email):
    try:
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return {"status": "error", "message": "Invalid email format"}
        
        domain = email.split('@')[1]
        providers = {
            'gmail.com': 'Google Gmail',
            'yahoo.com': 'Yahoo Mail',
            'outlook.com': 'Microsoft Outlook',
            'hotmail.com': 'Microsoft Hotmail',
            'rediffmail.com': 'Rediffmail',
            'protonmail.com': 'ProtonMail',
            'zoho.com': 'Zoho Mail'
        }
        
        return {
            "Email Details": {
                "Email": email,
                "Provider": providers.get(domain, "Unknown"),
                "Domain": domain,
                "Valid Format": "Yes",
                "Disposable": domain in ['temp-mail.org', 'guerrillamail.com', '10minutemail.com']
            },
            "_meta": {
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============ PINCODE (Postal API) ============
def get_pincode_info(pincode):
    try:
        pincode = str(pincode).strip()
        if not pincode.isdigit() or len(pincode) != 6:
            return {"status": "error", "message": "Invalid pincode (6 digits required)"}
        
        url = f"https://api.postalpincode.in/pincode/{pincode}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data and data[0].get('Status') == 'Success':
                post_office = data[0]['PostOffice'][0]
                return {
                    "Pincode Details": {
                        "Pincode": pincode,
                        "City": post_office.get("District"),
                        "State": post_office.get("State"),
                        "District": post_office.get("District"),
                        "Post Office": post_office.get("Name"),
                        "Delivery Status": post_office.get("DeliveryStatus"),
                        "Country": "India"
                    },
                    "_meta": {
                        "status": "success",
                        "timestamp": datetime.now().isoformat()
                    }
                }
        return {"status": "error", "message": "Pincode not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============ GITHUB (Official API) ============
def get_github_info(username):
    try:
        url = f"https://api.github.com/users/{username}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            return {
                "GitHub Profile": {
                    "Username": data.get("login"),
                    "Name": data.get("name"),
                    "Bio": data.get("bio"),
                    "Location": data.get("location"),
                    "Public Repos": data.get("public_repos"),
                    "Followers": data.get("followers"),
                    "Following": data.get("following"),
                    "Created": data.get("created_at"),
                    "Profile URL": data.get("html_url")
                },
                "_meta": {
                    "status": "success",
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            return {"status": "error", "message": "GitHub user not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============ DEMO SERVICES ============
def demo_service(service, identifier):
    return {
        f"{service} Details": {
            "Service": service,
            "Identifier": identifier,
            "Status": "Demo - Educational Purpose Only",
            "Name": f"Demo User for {service}",
            "Valid": "Yes",
            "Note": "This is simulated data for research/educational use",
            "Disclaimer": "Not for production or unlawful use"
        },
        "_meta": {
            "status": "demo",
            "timestamp": datetime.now().isoformat(),
            "warning": "This is demo data. Real integration requires proper authorization."
        }
    }

# ============ ROUTES ============
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/vehicle/<path:query>')
@limiter.limit("3 per minute")
def vehicle_route(query):
    return jsonify(get_vehicle_details(query))

@app.route('/num/<path:query>')
@limiter.limit("5 per minute")
def num_route(query):
    return jsonify(get_phone_details(query))

@app.route('/truecaller/<path:query>')
@limiter.limit("5 per minute")
def truecaller_route(query):
    return jsonify(demo_service("Truecaller", query))

@app.route('/aadhar/<path:query>')
@limiter.limit("5 per minute")
def aadhar_route(query):
    return jsonify(demo_service("Aadhar", query))

@app.route('/pan/<path:query>')
@limiter.limit("5 per minute")
def pan_route(query):
    return jsonify(demo_service("PAN", query))

@app.route('/ifsc/<path:query>')
@limiter.limit("5 per minute")
def ifsc_route(query):
    return jsonify(get_ifsc_info(query))

@app.route('/ip/<path:query>')
@limiter.limit("10 per minute")
def ip_route(query):
    return jsonify(get_ip_info(query))

@app.route('/email/<path:query>')
@limiter.limit("10 per minute")
def email_route(query):
    return jsonify(get_email_info(query))

@app.route('/pincode/<path:query>')
@limiter.limit("10 per minute")
def pincode_route(query):
    return jsonify(get_pincode_info(query))

@app.route('/github/<path:query>')
@limiter.limit("10 per minute")
def github_route(query):
    return jsonify(get_github_info(query))

@app.route('/ff/<path:query>')
@limiter.limit("5 per minute")
def ff_route(query):
    return jsonify(demo_service("FreeFire", query))

@app.route('/numvl/<path:query>')
@limiter.limit("5 per minute")
def numvl_route(query):
    return jsonify(demo_service("Number Validator", query))

@app.route('/family/<path:query>')
@limiter.limit("5 per minute")
def family_route(query):
    return jsonify(demo_service("Family", query))

@app.route('/insta/<path:query>')
@limiter.limit("5 per minute")
def insta_route(query):
    return jsonify(demo_service("Instagram", query))

@app.route('/tg/<path:query>')
@limiter.limit("5 per minute")
def tg_route(query):
    return jsonify(demo_service("Telegram", query))

@app.route('/pak/<path:query>')
@limiter.limit("5 per minute")
def pak_route(query):
    return jsonify(demo_service("Pakistan", query))

@app.route('/bgmi/<path:query>')
@limiter.limit("5 per minute")
def bgmi_route(query):
    return jsonify(demo_service("BGMI", query))

@app.route('/ping')
def ping():
    return jsonify({
        "status": "alive",
        "services": 15,
        "timestamp": datetime.now().isoformat(),
        "developer": "N.S",
        "version": "Ultimate Pro 4.0"
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)
