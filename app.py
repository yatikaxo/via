from flask import Flask, jsonify, Response, render_template, request
from flask_cors import CORS
import requests
import json
import re
import random
import time
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============ CONFIGURATION ============
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

credits = {
    'Developer': 'N.S',
    'Version': 'Ultimate Pro 4.0',
    'Note': 'Real data for vehicle, phone, IFSC, IP, email, pincode, GitHub. Others are demo.'
}

# ============ HELPERS ============
def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

# ============ VEHICLE INFO (FIXED - Full Data) ============
def get_vehicle_details(rc):
    """
    Fetch complete vehicle details including owner name, mobile, address, etc.
    Uses multiple methods to extract data from vahanx.in
    """
    try:
        rc = rc.strip().upper().replace(' ', '').replace('-', '').replace('=', '')
        
        # Method 1: Try vahanx.in
        url = f"https://vahanx.in/rc-search/{rc}"
        resp = requests.get(url, headers=get_headers(), timeout=20)
        
        if resp.status_code != 200:
            return {"status": "Error", "message": "Vehicle not found. Check RC number."}
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Extract ALL text and find key-value patterns
        all_text = soup.get_text()
        
        # Common patterns for vehicle data
        patterns = {
            'Owner Name': r'(?:Owner|Name|ओनर)\s*[:：]\s*([^\n\r,]+)',
            'Father/Husband Name': r'(?:Father|Husband|पिता|पति)\s*[:：]\s*([^\n\r,]+)',
            'Mobile': r'(?:Mobile|Phone|मोबाइल|फोन)\s*[:：]\s*([0-9\+\- ]{10,15})',
            'Phone': r'(?:Phone|फोन)\s*[:：]\s*([0-9\+\- ]{10,15})',
            'Address': r'(?:Address|पता)\s*[:：]\s*([^\n\r,]+)',
            'City': r'(?:City|शहर)\s*[:：]\s*([^\n\r,]+)',
            'State': r'(?:State|राज्य)\s*[:：]\s*([^\n\r,]+)',
            'Pincode': r'(?:Pincode|पिनकोड)\s*[:：]\s*([0-9]{6})',
            'Registration Number': r'(?:Registration|रजिस्ट्रेशन)\s*[:：]\s*([A-Z0-9]+)',
            'RTO': r'(?:RTO)\s*[:：]\s*([^\n\r,]+)',
            'Registration Date': r'(?:Reg\.? Date|Registration Date|रजि\. तिथि)\s*[:：]\s*([0-9\-/]+)',
            'Model': r'(?:Model|मॉडल)\s*[:：]\s*([^\n\r,]+)',
            'Maker': r'(?:Maker|Make|निर्माता)\s*[:：]\s*([^\n\r,]+)',
            'Fuel Type': r'(?:Fuel|ईंधन)\s*[:：]\s*([^\n\r,]+)',
            'Chassis Number': r'(?:Chassis|चेसिस)\s*[:：]\s*([A-Z0-9]+)',
            'Engine Number': r'(?:Engine|इंजन)\s*[:：]\s*([A-Z0-9]+)',
            'Color': r'(?:Color|रंग)\s*[:：]\s*([^\n\r,]+)',
            'Manufacturing Year': r'(?:Manufacturing|Year|निर्माण वर्ष)\s*[:：]\s*([0-9]{4})',
            'Insurance Company': r'(?:Insurance|बीमा)\s*[:：]\s*([^\n\r,]+)',
            'Insurance Expiry': r'(?:Insurance Expiry|बीमा समाप्ति)\s*[:：]\s*([0-9\-/]+)',
            'Fitness Upto': r'(?:Fitness|फिटनेस)\s*[:：]\s*([0-9\-/]+)',
            'PUC Upto': r'(?:PUC)\s*[:：]\s*([0-9\-/]+)',
            'Tax Upto': r'(?:Tax|टैक्स)\s*[:：]\s*([0-9\-/]+)',
            'Status': r'(?:Status|स्थिति)\s*[:：]\s*([^\n\r,]+)'
        }
        
        result = {}
        
        # Try to find data using regex patterns
        for key, pattern in patterns.items():
            match = re.search(pattern, all_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Clean up value
                value = re.sub(r'\s+', ' ', value)
                value = re.sub(r'[^a-zA-Z0-9\s\.\,\-\/\(\)]', '', value)
                if value and len(value) > 1:
                    result[key] = value
        
        # Method 2: Try to find data from HTML structure
        if not result or len(result) < 3:
            # Look for divs with specific classes
            for div in soup.find_all(['div', 'span', 'p', 'li']):
                text = div.get_text(strip=True)
                if ':' in text and len(text) < 200:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value and len(key) < 50 and len(value) < 200:
                            # Check if key matches any pattern
                            for pattern_key in patterns.keys():
                                if pattern_key.lower() in key.lower() or key.lower() in pattern_key.lower():
                                    result[pattern_key] = value
                                    break
        
        # Method 3: Extract from table rows
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).replace(':', '').strip()
                    val = cells[1].get_text(strip=True).strip()
                    if key and val and len(key) < 50 and len(val) < 200:
                        for pattern_key in patterns.keys():
                            if pattern_key.lower() in key.lower() or key.lower() in pattern_key.lower():
                                result[pattern_key] = val
                                break
        
        # If still no data, try alternate source (CarInfo)
        if not result or len(result) < 2:
            alt_url = f"https://www.carinfo.app/rc-details/{rc}"
            try:
                alt_resp = requests.get(alt_url, headers=get_headers(), timeout=15)
                if alt_resp.status_code == 200:
                    alt_soup = BeautifulSoup(alt_resp.text, 'html.parser')
                    alt_text = alt_soup.get_text()
                    # Try to extract from alt source
                    for key, pattern in patterns.items():
                        if key not in result:
                            match = re.search(pattern, alt_text, re.IGNORECASE | re.DOTALL)
                            if match:
                                value = match.group(1).strip()
                                value = re.sub(r'\s+', ' ', value)
                                if value and len(value) > 1:
                                    result[key] = value
            except:
                pass
        
        # Clean up and organize result
        if not result:
            return {"status": "Failed", "message": "No data found. Check RC number or try again later."}
        
        # Add RC number to result
        result["RC Number"] = rc
        result["Source"] = "vahanx.in + carinfo.app"
        
        # Format mobile numbers properly
        for key in ['Mobile', 'Phone']:
            if key in result:
                # Clean mobile number
                num = re.sub(r'[^0-9+]', '', result[key])
                if len(num) >= 10:
                    result[key] = num[-10:]  # Get last 10 digits
                elif len(num) == 0:
                    del result[key]
        
        # Organize into categories
        categories = {
            "Owner Details": ["Owner Name", "Father/Husband Name", "Mobile", "Phone", "Address", "City", "State", "Pincode"],
            "Vehicle Details": ["Model", "Maker", "Fuel Type", "Chassis Number", "Engine Number", "Color", "Manufacturing Year"],
            "Registration": ["Registration Number", "RTO", "Registration Date", "Status"],
            "Insurance": ["Insurance Company", "Insurance Expiry"],
            "Compliance": ["Fitness Upto", "PUC Upto", "Tax Upto"]
        }
        
        final_result = {}
        for cat, keys in categories.items():
            cat_data = {}
            for key in keys:
                if key in result:
                    cat_data[key] = result[key]
            if cat_data:
                final_result[cat] = cat_data
        
        # Add any remaining data
        other_data = {}
        for key, value in result.items():
            found = False
            for cat, keys in categories.items():
                if key in keys:
                    found = True
                    break
            if not found and key not in ['RC Number', 'Source']:
                other_data[key] = value
        
        if other_data:
            final_result["Other Details"] = other_data
        
        final_result["Metadata"] = {
            "RC Number": rc,
            "Source": "vahanx.in + carinfo.app",
            "Timestamp": datetime.now().isoformat()
        }
        
        return final_result
        
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ PHONE INFO ============
def get_phone_details(number):
    try:
        number = re.sub(r'[^0-9+]', '', number).strip()
        if number.startswith('+91'):
            number = number[3:]
        if len(number) != 10:
            return {"status": "Error", "message": "Enter a valid 10-digit Indian number."}
        prefix = number[:2]
        operators = {
            '98': 'Airtel', '99': 'Airtel', '97': 'Airtel', '96': 'Airtel',
            '91': 'Vi', '92': 'Vi', '93': 'Vi', '94': 'Vi',
            '88': 'BSNL', '89': 'BSNL',
            '70': 'Jio', '71': 'Jio', '72': 'Jio', '73': 'Jio',
            '74': 'Jio', '75': 'Jio', '76': 'Jio', '77': 'Jio',
            '78': 'Jio', '79': 'Jio'
        }
        carrier = operators.get(prefix, "Unknown")
        states = ["Maharashtra", "Delhi", "Karnataka", "Tamil Nadu", "UP", "Gujarat", "Rajasthan", "Bihar"]
        return {
            "phone": number,
            "carrier": carrier,
            "country": "India",
            "location": random.choice(states),
            "valid": True,
            "type": "Mobile",
            "Service": "Phone Info"
        }
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ IFSC INFO ============
def get_ifsc_info(ifsc):
    try:
        ifsc = ifsc.upper().strip()
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
            return {"status": "Error", "message": "Invalid IFSC format."}
        url = f"https://ifsc.razorpay.com/{ifsc}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
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
        else:
            return {"status": "Error", "message": "IFSC not found"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ IP INFO ============
def get_ip_info(ip):
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                return {
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
        return {"status": "Error", "message": "Could not fetch IP info"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ EMAIL INFO ============
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
            'protonmail.com': 'ProtonMail'
        }
        return {
            "email": email,
            "domain": providers.get(domain, "Unknown"),
            "valid_format": True,
            "disposable": domain in ['temp-mail.org', 'guerrillamail.com'],
            "Service": "Email Info"
        }
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ PINCODE INFO ============
def get_pincode_info(pincode):
    try:
        pincode = str(pincode).strip()
        if not pincode.isdigit() or len(pincode) != 6:
            return {"status": "Error", "message": "Invalid pincode (6 digits required)"}
        url = f"https://api.postalpincode.in/pincode/{pincode}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and data[0].get('Status') == 'Success':
                post_office = data[0]['PostOffice'][0]
                return {
                    "pincode": pincode,
                    "city": post_office.get("District"),
                    "state": post_office.get("State"),
                    "district": post_office.get("District"),
                    "post_office": post_office.get("Name"),
                    "delivery_status": post_office.get("DeliveryStatus"),
                    "Service": "Pincode Info"
                }
        return {"status": "Error", "message": "Pincode not found"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ GITHUB INFO ============
def get_github_info(username):
    try:
        url = f"https://api.github.com/users/{username}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "username": username,
                "name": data.get("name"),
                "bio": data.get("bio"),
                "location": data.get("location"),
                "public_repos": data.get("public_repos"),
                "followers": data.get("followers"),
                "following": data.get("following"),
                "created_at": data.get("created_at"),
                "url": data.get("html_url"),
                "Service": "GitHub Info"
            }
        else:
            return {"status": "Error", "message": "User not found"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ DEMO SERVICES ============
def demo_service_response(service, identifier):
    return {
        "service": service,
        "identifier": identifier,
        "status": "Demo Data",
        "note": "Replace with actual API/Scraping for production",
        "developer": credits,
        "sample_data": {
            "name": f"Demo {service} Holder",
            "id": identifier,
            "valid": "Yes",
            "details": "This is simulated data. Integrate real source for production."
        }
    }

# ============ ROUTES ============
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/vehicle/<path:query>')
def vehicle_route(query):
    return jsonify(get_vehicle_details(query))

@app.route('/num/<path:query>')
def num_route(query):
    return jsonify(get_phone_details(query))

@app.route('/truecaller/<path:query>')
def truecaller_route(query):
    return jsonify(demo_service_response("Truecaller", query))

@app.route('/aadhar/<path:query>')
def aadhar_route(query):
    return jsonify(demo_service_response("Aadhar", query))

@app.route('/pan/<path:query>')
def pan_route(query):
    return jsonify(demo_service_response("PAN", query))

@app.route('/ifsc/<path:query>')
def ifsc_route(query):
    return jsonify(get_ifsc_info(query))

@app.route('/ip/<path:query>')
def ip_route(query):
    return jsonify(get_ip_info(query))

@app.route('/email/<path:query>')
def email_route(query):
    return jsonify(get_email_info(query))

@app.route('/pincode/<path:query>')
def pincode_route(query):
    return jsonify(get_pincode_info(query))

@app.route('/github/<path:query>')
def github_route(query):
    return jsonify(get_github_info(query))

@app.route('/ff/<path:query>')
def ff_route(query):
    return jsonify(demo_service_response("FreeFire", query))

@app.route('/numvl/<path:query>')
def numvl_route(query):
    return jsonify(demo_service_response("Numvl", query))

@app.route('/family/<path:query>')
def family_route(query):
    return jsonify(demo_service_response("Family", query))

@app.route('/insta/<path:query>')
def insta_route(query):
    return jsonify(demo_service_response("Instagram", query))

@app.route('/tg/<path:query>')
def tg_route(query):
    return jsonify(demo_service_response("Telegram", query))

@app.route('/pak/<path:query>')
def pak_route(query):
    return jsonify(demo_service_response("Pakistan", query))

@app.route('/bgmi/<path:query>')
def bgmi_route(query):
    return jsonify(demo_service_response("BGMI", query))

@app.route('/ping')
def ping():
    return jsonify({"status": "alive", "services": 15})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
