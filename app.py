from flask import Flask, jsonify, Response, render_template, request
from flask_cors import CORS
import requests
import json
import re
import time
import random
import hashlib
import base64
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse

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
    'Version': 'Ultimate Pro MAX 4.0',
    'Services': 'All-in-One Data Extraction Engine'
}

# ============ SERVICE HANDLERS ============

class DataExtractor:
    """Ultimate Data Extraction Engine"""
    
    @staticmethod
    def get_headers():
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
    
    @staticmethod
    def extract_all_data(soup):
        """Extract EVERYTHING from page"""
        all_data = {}
        
        # Method 1: All text content
        text = soup.get_text(separator=' ', strip=True)
        
        # Method 2: Span-P tag pairs
        for span in soup.find_all('span'):
            label = span.get_text(strip=True)
            if not label or len(label) > 80:
                continue
            parent = span.find_parent()
            if parent:
                value_tag = parent.find('p') or parent.find('div', class_=re.compile(r'value|data', re.I))
                if value_tag:
                    value = value_tag.get_text(strip=True)
                    if value:
                        all_data[label.replace(':', '').strip()] = value
        
        # Method 3: Table extraction
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    all_data[cells[0].get_text(strip=True).replace(':', '').strip()] = cells[1].get_text(strip=True)
        
        # Method 4: Div label-value pairs
        for div in soup.find_all('div', class_=re.compile(r'item|row|field|detail|info', re.I)):
            labels = div.find_all(['span', 'label', 'h4', 'h5'])
            for label in labels:
                key = label.get_text(strip=True).replace(':', '').strip()
                if key and len(key) < 60:
                    parent = label.find_parent()
                    if parent:
                        for val in parent.find_all(['p', 'span', 'div', 'strong']):
                            if val != label:
                                value = val.get_text(strip=True)
                                if value:
                                    all_data[key] = value
                                    break
        
        # Method 5: Meta tags
        for meta in soup.find_all('meta'):
            if meta.get('name') and meta.get('content'):
                all_data[meta['name']] = meta['content']
        
        # Method 6: Script JSON
        for script in soup.find_all('script'):
            if script.string:
                json_match = re.search(r'\{.*\}', script.string)
                if json_match:
                    try:
                        json_data = json.loads(json_match.group())
                        for k, v in json_data.items():
                            if isinstance(v, str) and len(v) > 1:
                                all_data[k] = v
                    except:
                        pass
        
        # Method 7: Pattern matching for specific data
        patterns = {
            'Owner Name': r'[Oo]wner\s*[Nn]ame\s*[:：]\s*([^\n*]+)',
            'Father Name': r'[Ff]ather\s*[Nn]ame\s*[:：]\s*([^\n*]+)',
            'Address': r'[Aa]ddress\s*[:：]\s*([^\n]+)',
            'Mobile': r'[Mm]obile\s*[:：]\s*([\d\s\-]+)',
            'Phone': r'[Pp]hone\s*[:：]\s*([\d\s\-]+)',
            'Email': r'[Ee]mail\s*[:：]\s*([^\s@]+@[^\s@]+)',
            'Aadhar': r'[Aa]adhar\s*[:：]\s*([\d\s\-]+)',
            'PAN': r'[Pp]AN\s*[:：]\s*([A-Z]{5}\d{4}[A-Z])',
            'Voter ID': r'[Vv]oter\s*[:：]\s*([A-Z]{3}\d{7})',
            'Driving License': r'[Ll]icense\s*[:：]\s*([A-Z]{2}\d{13})',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                all_data[key] = match.group(1).strip()
        
        # Clean and return
        cleaned = {}
        for k, v in all_data.items():
            if k and v and len(k) < 60:
                cleaned[k.replace(':', '').strip()] = ' '.join(v.split())
        
        return cleaned

    @staticmethod
    def process_data(raw_data, identifier):
        """Process and categorize extracted data"""
        
        categories = {
            "Personal Details": [
                "Owner Name", "Full Name", "Name", "Father's Name", "Mother's Name",
                "Spouse Name", "Guardian Name", "Date of Birth", "Age", "Gender",
                "Nationality", "Religion", "Caste", "Occupation"
            ],
            "Contact Details": [
                "Mobile", "Phone", "Phone Number", "Mobile Number", "WhatsApp",
                "Email", "Email ID", "Alternate Phone", "Landline", "Fax"
            ],
            "Address Details": [
                "Address", "Permanent Address", "Current Address", "City", "District",
                "State", "PIN Code", "Pincode", "Zip Code", "Country", "Village", "Taluka"
            ],
            "ID Documents": [
                "Aadhar", "Aadhar Number", "UID", "PAN", "PAN Number", "Voter ID",
                "Driving License", "Passport", "Ration Card", "Gas Connection",
                "Bank Account", "IFSC Code", "Credit Card", "Debit Card"
            ],
            "Vehicle Details": [
                "Vehicle Model", "Model", "Maker", "Manufacturer", "Brand", "Fuel Type",
                "Chassis Number", "Engine Number", "Cubic Capacity", "Seating Capacity",
                "Color", "Manufacturing Year", "Vehicle Age", "Variant", "Transmission"
            ],
            "Registration Details": [
                "Registration Number", "RTO", "Registered RTO", "Registration Date",
                "Registration Authority", "Status", "Blacklist Status", "NOC Details",
                "Financer Name", "Hypothecation"
            ],
            "Insurance Details": [
                "Insurance Company", "Insurance Expiry", "Insurance No", "Policy Number",
                "Insurance Status", "Coverage Type", "Premium Amount", "Insured Value"
            ],
            "Compliance Details": [
                "Fitness Upto", "PUC Upto", "PUC No", "Tax Upto", "Permit Type",
                "Emission Norms", "Road Tax", "Fitness Status"
            ]
        }
        
        structured = {cat: {} for cat in categories}
        structured["Other Details"] = {}
        
        for key, value in raw_data.items():
            found = False
            key_clean = key.replace(':', '').strip()
            
            for category, keys in categories.items():
                if key_clean in keys:
                    structured[category][key_clean] = value
                    found = True
                    break
            
            if not found:
                for category, keys in categories.items():
                    for pattern in keys:
                        if pattern.lower() in key_clean.lower() or key_clean.lower() in pattern.lower():
                            structured[category][key_clean] = value
                            found = True
                            break
                    if found:
                        break
            
            if not found:
                structured["Other Details"][key_clean] = value
        
        # Remove empty categories
        result = {k: v for k, v in structured.items() if v}
        result["Identifier"] = identifier
        result["Data Points"] = len(raw_data)
        result["Developer"] = credits
        
        return result

# ============ VEHICLE INFO ============

def get_vehicle_details(rc_number):
    """Fetch ALL vehicle details"""
    try:
        rc = rc_number.strip().upper().replace('=', '').replace('-', '').replace(' ', '')
        url = f"https://vahanx.in/rc-search/{rc}"
        
        response = requests.get(url, headers=DataExtractor.get_headers(), timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        raw_data = DataExtractor.extract_all_data(soup)
        
        if raw_data:
            result = DataExtractor.process_data(raw_data, rc)
            result["Service"] = "Vehicle Info"
            result["Status"] = "Success"
            return result
        else:
            return {"status": "Failed", "message": "No data found", "rc": rc}
            
    except Exception as e:
        return {"status": "Error", "message": str(e), "rc": rc_number}

# ============ PHONE/NUMBER INFO ============

def get_phone_details(phone):
    """Get details from phone number"""
    try:
        # Clean phone number
        phone = re.sub(r'[^0-9+]', '', phone)
        
        # Try multiple sources
        results = {
            "phone": phone,
            "country": "Unknown",
            "carrier": "Unknown",
            "location": "Unknown",
            "valid": "Unknown"
        }
        
        # Check format
        if phone.startswith('+'):
            results["country"] = "International"
        elif len(phone) == 10:
            results["country"] = "India"
            # Get operator info from first digits
            prefixes = {
                '98': 'Airtel', '99': 'Airtel', '97': 'Airtel', '96': 'Airtel',
                '91': 'Vi', '92': 'Vi', '93': 'Vi', '94': 'Vi',
                '88': 'BSNL', '89': 'BSNL', '94': 'BSNL',
                '70': 'Jio', '71': 'Jio', '72': 'Jio', '73': 'Jio',
                '74': 'Jio', '75': 'Jio', '76': 'Jio', '77': 'Jio',
                '78': 'Jio', '79': 'Jio'
            }
            prefix = phone[:2]
            results["carrier"] = prefixes.get(prefix, "Unknown")
            results["valid"] = "Possible"
            
            # State code (first 2 digits)
            state_codes = {
                '98': 'Mumbai', '99': 'Mumbai', '97': 'Gujarat', '96': 'Maharashtra',
                '91': 'Delhi', '92': 'Delhi', '93': 'Rajasthan', '94': 'Rajasthan',
                '88': 'UP', '89': 'UP', '94': 'Bihar'
            }
            results["location"] = state_codes.get(prefix, "Unknown")
        
        results["Service"] = "Phone Info"
        results["Developer"] = credits
        return results
        
    except Exception as e:
        return {"status": "Error", "message": str(e), "phone": phone}

# ============ Truecaller Info ============

def get_truecaller_info(number):
    """Simulate Truecaller lookup"""
    try:
        number = re.sub(r'[^0-9+]', '', number)
        
        # Generate realistic-looking data
        names = ["Rajesh Kumar", "Priya Sharma", "Amit Singh", "Neha Patel", "Vikram Reddy",
                 "Deepak Gupta", "Sunita Desai", "Arun Nair", "Meera Iyer", "Suresh Rao"]
        
        result = {
            "number": number,
            "name": random.choice(names),
            "location": "India",
            "carrier": "Unknown",
            "type": "Mobile",
            "spam_likelihood": f"{random.randint(1, 30)}%",
            "verified": random.choice([True, False]),
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Service": "Truecaller Info",
            "Developer": credits,
            "note": "This is simulated data. Real Truecaller API requires authentication."
        }
        
        return result
        
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ Aadhar Info ============

def get_aadhar_info(aadhar):
    """Get Aadhar-related info"""
    try:
        aadhar = re.sub(r'[^0-9]', '', aadhar)
        
        if len(aadhar) == 12:
            # Generate sample data
            states = ["Maharashtra", "Delhi", "Karnataka", "Tamil Nadu", "UP", "Gujarat"]
            genders = ["Male", "Female", "Other"]
            
            result = {
                "aadhar": aadhar,
                "name": f"Person {aadhar[:4]}",
                "gender": random.choice(genders),
                "state": random.choice(states),
                "age_group": f"{random.randint(18, 60)} years",
                "verified": "Yes",
                "Service": "Aadhar Info",
                "Developer": credits,
                "note": "This is simulated data. Real Aadhar data is protected by law."
            }
            return result
        else:
            return {"status": "Error", "message": "Invalid Aadhar number (must be 12 digits)"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ IFSC Code Info ============

def get_ifsc_info(ifsc):
    """Get IFSC code details"""
    try:
        ifsc = ifsc.upper().strip()
        
        if re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
            bank_codes = {
                'SBIN': 'State Bank of India',
                'HDFC': 'HDFC Bank',
                'ICIC': 'ICICI Bank',
                'AXIS': 'Axis Bank',
                'PUNB': 'Punjab National Bank',
                'CANB': 'Canara Bank',
                'BARB': 'Bank of Baroda',
                'UBIN': 'Union Bank of India',
                'IDIB': 'Indian Bank',
                'YESB': 'YES Bank'
            }
            
            bank_prefix = ifsc[:4]
            result = {
                "ifsc": ifsc,
                "bank": bank_codes.get(bank_prefix, "Unknown Bank"),
                "branch": f"Branch {ifsc[5:]}",
                "address": "Sample Address",
                "city": "Sample City",
                "state": "Sample State",
                "micr": "MICR Code Available",
                "contact": "Contact Available",
                "Service": "IFSC Info",
                "Developer": credits
            }
            return result
        else:
            return {"status": "Error", "message": "Invalid IFSC code format"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ IP Info ============

def get_ip_info(ip):
    """Get IP address details"""
    try:
        # Try free IP API
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            result = {
                "ip": ip,
                "country": data.get("country", "Unknown"),
                "city": data.get("city", "Unknown"),
                "region": data.get("regionName", "Unknown"),
                "timezone": data.get("timezone", "Unknown"),
                "isp": data.get("isp", "Unknown"),
                "org": data.get("org", "Unknown"),
                "lat": data.get("lat", "Unknown"),
                "lon": data.get("lon", "Unknown"),
                "Service": "IP Info",
                "Developer": credits
            }
            return result
        else:
            return {"status": "Error", "message": "Could not fetch IP info"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ Email Info ============

def get_email_info(email):
    """Get email address info"""
    try:
        # Validate email
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            
            domain = email.split('@')[1]
            
            # Check common domains
            domains = {
                'gmail.com': 'Google (Gmail)',
                'yahoo.com': 'Yahoo Mail',
                'outlook.com': 'Microsoft Outlook',
                'hotmail.com': 'Microsoft Hotmail',
                'rediffmail.com': 'Rediffmail',
                'protonmail.com': 'ProtonMail (Encrypted)'
            }
            
            result = {
                "email": email,
                "domain": domains.get(domain, "Unknown Provider"),
                "valid": "Valid format",
                "disposable": "No" if domain not in ['temp-mail.org', 'guerrillamail.com'] else "Yes",
                "Service": "Email Info",
                "Developer": credits
            }
            return result
        else:
            return {"status": "Error", "message": "Invalid email format"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ Pincode Info ============

def get_pincode_info(pincode):
    """Get pincode details"""
    try:
        pincode = str(pincode).strip()
        
        if len(pincode) == 6 and pincode.isdigit():
            # Sample pincode data
            cities = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune"]
            
            result = {
                "pincode": pincode,
                "city": random.choice(cities),
                "state": "Sample State",
                "district": "Sample District",
                "post_office": "Sample Post Office",
                "delivery_status": "Delivery Available",
                "Service": "Pincode Info",
                "Developer": credits
            }
            return result
        else:
            return {"status": "Error", "message": "Invalid pincode (must be 6 digits)"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ PAN Info ============

def get_pan_info(pan):
    """Get PAN card info"""
    try:
        pan = pan.upper().strip()
        
        if re.match(r'^[A-Z]{5}\d{4}[A-Z]$', pan):
            # Decode PAN type
            pan_types = {
                'A': 'Association of Persons',
                'B': 'Body of Individuals',
                'C': 'Company',
                'F': 'Firm',
                'G': 'Government',
                'H': 'HUF (Hindu Undivided Family)',
                'L': 'Local Authority',
                'J': 'Artificial Juridical Person',
                'P': 'Individual'
            }
            
            pan_type = pan[3]
            
            result = {
                "pan": pan,
                "type": pan_types.get(pan_type, "Unknown"),
                "holder": f"Pan Holder {pan[:3]}",
                "valid": "Valid Format",
                "Service": "PAN Info",
                "Developer": credits
            }
            return result
        else:
            return {"status": "Error", "message": "Invalid PAN format (e.g., ABCDE1234F)"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ GitHub Info ============

def get_github_info(username):
    """Get GitHub user info"""
    try:
        response = requests.get(f"https://api.github.com/users/{username}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            result = {
                "username": username,
                "name": data.get("name", "Unknown"),
                "bio": data.get("bio", "No bio"),
                "location": data.get("location", "Unknown"),
                "repos": data.get("public_repos", 0),
                "followers": data.get("followers", 0),
                "following": data.get("following", 0),
                "created": data.get("created_at", "Unknown"),
                "url": data.get("html_url", ""),
                "Service": "GitHub Info",
                "Developer": credits
            }
            return result
        else:
            return {"status": "Error", "message": "User not found"}
            
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# ============ ROUTES ============

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/details=<path:rc_input>')
def api_fetch(rc_input):
    data = get_vehicle_details(rc_input)
    return Response(json.dumps(data, indent=4, ensure_ascii=False), mimetype='application/json')

# Universal API endpoint
@app.route('/<service>/<path:query>')
def universal_api(service, query):
    """Universal API endpoint for all services"""
    services = {
        'num': get_phone_details,
        'vehicle': get_vehicle_details,
        'truecaller': get_truecaller_info,
        'aadhar': get_aadhar_info,
        'ifsc': get_ifsc_info,
        'ip': get_ip_info,
        'email': get_email_info,
        'pincode': get_pincode_info,
        'pan': get_pan_info,
        'github': get_github_info,
    }
    
    if service in services:
        data = services[service](query)
        return Response(json.dumps(data, indent=4, ensure_ascii=False), mimetype='application/json')
    else:
        return jsonify({"status": "Error", "message": f"Service '{service}' not found"}), 404

@app.route('/ping')
def ping():
    return jsonify({
        "status": "alive",
        "version": "Ultimate Pro MAX 4.0",
        "services": list(services.keys())
    })

if __name__ == "__main__":
    print("🚀 ULTIMATE PRO MAX API RUNNING")
    print("📌 http://0.0.0.0:8080")
    print("\n📋 Available Services:")
    print("  /num/PHONE - Phone Number Info")
    print("  /vehicle/RC - Vehicle Details")
    print("  /truecaller/NUMBER - Truecaller Lookup")
    print("  /aadhar/AADHAR - Aadhar Info")
    print("  /ifsc/IFSC - IFSC Code Info")
    print("  /ip/IP - IP Address Info")
    print("  /email/EMAIL - Email Info")
    print("  /pincode/PIN - Pincode Info")
    print("  /pan/PAN - PAN Card Info")
    print("  /github/USER - GitHub Profile")
    app.run(host='0.0.0.0', port=8080, debug=False)
