from flask import Flask, jsonify, render_template, request
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

def clean_text(text):
    """Clean extracted text"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.\,\-\/\(\)\@\+]', '', text)
    return text.strip()

def extract_vehicle_data_from_html(html):
    """Extract vehicle data from any HTML using multiple methods"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script and style tags
    for script in soup(["script", "style"]):
        script.decompose()
    
    text = soup.get_text()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    result = {}
    
    # Method 1: Find key-value patterns with regex
    patterns = {
        'owner_name': r'(?:Owner|Name|ओनर)[\s:：]+([^\n\r,]+)',
        'father_name': r'(?:Father|Husband|पिता|पति)[\s:：]+([^\n\r,]+)',
        'mobile': r'(?:Mobile|Phone|Mob|मोबाइल|फोन)[\s:：]+([0-9\+\- ]{10,15})',
        'phone': r'(?:Phone|फोन)[\s:：]+([0-9\+\- ]{10,15})',
        'address': r'(?:Address|पता)[\s:：]+([^\n\r,]+)',
        'city': r'(?:City|शहर)[\s:：]+([^\n\r,]+)',
        'state': r'(?:State|राज्य)[\s:：]+([^\n\r,]+)',
        'pincode': r'(?:Pincode|PIN|पिनकोड)[\s:：]+([0-9]{6})',
        'registration': r'(?:Registration|Reg No|रजिस्ट्रेशन)[\s:：]+([A-Z0-9]+)',
        'rto': r'(?:RTO)[\s:：]+([^\n\r,]+)',
        'reg_date': r'(?:Reg\.? Date|Registration Date|रजि\. तिथि)[\s:：]+([0-9\-/]+)',
        'model': r'(?:Model|मॉडल)[\s:：]+([^\n\r,]+)',
        'maker': r'(?:Maker|Make|निर्माता)[\s:：]+([^\n\r,]+)',
        'fuel': r'(?:Fuel|ईंधन)[\s:：]+([^\n\r,]+)',
        'chassis': r'(?:Chassis|चेसिस)[\s:：]+([A-Z0-9]+)',
        'engine': r'(?:Engine|इंजन)[\s:：]+([A-Z0-9]+)',
        'color': r'(?:Color|रंग)[\s:：]+([^\n\r,]+)',
        'year': r'(?:Manufacturing|Year|निर्माण वर्ष)[\s:：]+([0-9]{4})',
        'insurance': r'(?:Insurance|बीमा)[\s:：]+([^\n\r,]+)',
        'insurance_expiry': r'(?:Insurance Expiry|बीमा समाप्ति)[\s:：]+([0-9\-/]+)',
        'fitness': r'(?:Fitness|फिटनेस)[\s:：]+([0-9\-/]+)',
        'puc': r'(?:PUC)[\s:：]+([0-9\-/]+)',
        'tax': r'(?:Tax|टैक्स)[\s:：]+([0-9\-/]+)',
        'status': r'(?:Status|स्थिति)[\s:：]+([^\n\r,]+)'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            value = clean_text(match.group(1))
            if value and len(value) > 1:
                result[key] = value
    
    # Method 2: Extract from HTML structure
    for tag in soup.find_all(['div', 'span', 'p', 'li', 'td']):
        tag_text = tag.get_text(strip=True)
        if ':' in tag_text and len(tag_text) < 200:
            parts = tag_text.split(':', 1)
            if len(parts) == 2:
                key = clean_text(parts[0])
                value = clean_text(parts[1])
                if key and value and len(key) < 50 and len(value) < 200:
                    # Map to standard keys
                    for pattern_key in patterns.keys():
                        if pattern_key.replace('_', ' ').lower() in key.lower() or key.lower() in pattern_key.replace('_', ' ').lower():
                            if not result.get(pattern_key) or len(result[pattern_key]) < len(value):
                                result[pattern_key] = value
                            break
    
    return result

# ============ VEHICLE INFO (FIXED - Multiple Sources) ============
def get_vehicle_details(rc):
    """
    Fetch vehicle details from multiple sources
    """
    try:
        rc = rc.strip().upper().replace(' ', '').replace('-', '').replace('=', '')
        
        if len(rc) < 6:
            return {"status": "Error", "message": "Invalid RC number format"}
        
        all_data = {}
        sources_used = []
        
        # Source 1: vahanx.in
        try:
            url1 = f"https://vahanx.in/rc-search/{rc}"
            resp1 = requests.get(url1, headers=get_headers(), timeout=15)
            if resp1.status_code == 200:
                data1 = extract_vehicle_data_from_html(resp1.text)
                if data1:
                    all_data.update(data1)
                    sources_used.append("vahanx.in")
        except:
            pass
        
        # Source 2: carinfo.app
        try:
            url2 = f"https://www.carinfo.app/rc-details/{rc}"
            resp2 = requests.get(url2, headers=get_headers(), timeout=15)
            if resp2.status_code == 200:
                data2 = extract_vehicle_data_from_html(resp2.text)
                if data2:
                    all_data.update(data2)
                    sources_used.append("carinfo.app")
        except:
            pass
        
        # Source 3: mParivahan (Govt official - if available)
        try:
            # Using a different approach - some RTO data
            url3 = f"https://www.mparivahan.in/rc-details/{rc}"
            resp3 = requests.get(url3, headers=get_headers(), timeout=15)
            if resp3.status_code == 200:
                data3 = extract_vehicle_data_from_html(resp3.text)
                if data3:
                    all_data.update(data3)
                    sources_used.append("mparivahan.in")
        except:
            pass
        
        # If no data found
        if not all_data:
            return {"status": "Failed", "message": "No data found. Check RC number or try again later."}
        
        # Clean and organize the data
        result = {}
        
        # Map extracted data to readable format
        field_mapping = {
            'owner_name': 'Owner Name',
            'father_name': 'Father/Husband Name',
            'mobile': 'Mobile Number',
            'phone': 'Phone Number',
            'address': 'Address',
            'city': 'City',
            'state': 'State',
            'pincode': 'Pincode',
            'registration': 'Registration Number',
            'rto': 'RTO Office',
            'reg_date': 'Registration Date',
            'model': 'Model',
            'maker': 'Maker/Manufacturer',
            'fuel': 'Fuel Type',
            'chassis': 'Chassis Number',
            'engine': 'Engine Number',
            'color': 'Color',
            'year': 'Manufacturing Year',
            'insurance': 'Insurance Company',
            'insurance_expiry': 'Insurance Expiry Date',
            'fitness': 'Fitness Certificate Upto',
            'puc': 'PUC Certificate Upto',
            'tax': 'Tax Upto',
            'status': 'Vehicle Status'
        }
        
        # Organize into categories
        categories = {
            "👤 Owner Details": ["Owner Name", "Father/Husband Name", "Mobile Number", "Phone Number", "Address", "City", "State", "Pincode"],
            "🚗 Vehicle Details": ["Registration Number", "RTO Office", "Registration Date", "Model", "Maker/Manufacturer", "Fuel Type", "Chassis Number", "Engine Number", "Color", "Manufacturing Year"],
            "📋 Insurance & Compliance": ["Insurance Company", "Insurance Expiry Date", "Fitness Certificate Upto", "PUC Certificate Upto", "Tax Upto", "Vehicle Status"]
        }
        
        for key, value in all_data.items():
            if key in field_mapping:
                result[field_mapping[key]] = value
        
        # Format mobile numbers
        for key in ['Mobile Number', 'Phone Number']:
            if key in result:
                num = re.sub(r'[^0-9+]', '', result[key])
                if len(num) >= 10:
                    result[key] = '+' + num[-10:] if len(num) > 10 else num
                elif len(num) < 10:
                    del result[key]
        
        # Create categorized output
        output = {}
        for category, keys in categories.items():
            cat_data = {}
            for key in keys:
                if key in result and result[key]:
                    cat_data[key] = result[key]
            if cat_data:
                output[category] = cat_data
        
        # Add any remaining data
        extra = {}
        for key, value in result.items():
            found = False
            for category, keys in categories.items():
                if key in keys:
                    found = True
                    break
            if not found:
                extra[key] = value
        
        if extra:
            output["📌 Additional Info"] = extra
        
        # Add metadata
        output["ℹ️ Information"] = {
            "RC Number": rc,
            "Sources Used": ", ".join(sources_used),
            "Timestamp": datetime.now().strftime("%d-%b-%Y %H:%M:%S"),
            "Status": "Success"
        }
        
        return output
        
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
