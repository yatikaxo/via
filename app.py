from flask import Flask, jsonify, Response, render_template, request
from flask_cors import CORS
import requests
import json
import re
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import hashlib

app = Flask(__name__)
CORS(app)

# Configuration
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
]

credits = {
    'Developer': 'N.S',
    'Version': 'Ultimate Pro 3.0',
    'Features': 'Full Data Extraction, Hidden Fields, Owner Details'
}

def get_random_headers():
    """Generate random headers to avoid blocking"""
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
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/"
    }

def extract_all_data(soup, rc):
    """Extract EVERY possible piece of data from the page"""
    all_data = {}
    
    # 1. Extract ALL text content
    text_content = soup.get_text(separator=' ', strip=True)
    
    # 2. Find ALL span elements with labels
    spans = soup.find_all('span')
    for span in spans:
        label = span.get_text(strip=True)
        if not label or len(label) > 100:
            continue
            
        # Find parent div
        parent = span.find_parent('div')
        if parent:
            # Check for value in p tag
            value_tag = parent.find('p')
            if value_tag:
                value = value_tag.get_text(strip=True)
                clean_label = label.replace(':', '').strip()
                if clean_label and value:
                    all_data[clean_label] = value
            
            # Check for value in div
            value_tag = parent.find('div', class_=re.compile(r'value|data|info|detail', re.I))
            if value_tag and not all_data.get(label):
                value = value_tag.get_text(strip=True)
                if value:
                    all_data[label.replace(':', '').strip()] = value
            
            # Check for value in any element
            for child in parent.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong']):
                if child != span and child.get_text(strip=True):
                    value = child.get_text(strip=True)
                    if value and len(value) < 200:
                        all_data[label.replace(':', '').strip()] = value
                        break

    # 3. Find ALL divs with data attributes
    divs = soup.find_all('div', class_=re.compile(r'item|row|field|detail|info|data|result|card|box|container|wrapper', re.I))
    for div in divs:
        # Try to find label and value pairs
        label_tags = div.find_all(['span', 'label', 'div', 'h4', 'h5', 'h6', 'strong'], class_=re.compile(r'label|key|title|name|heading', re.I))
        value_tags = div.find_all(['span', 'p', 'div', 'strong', 'td', 'li'], class_=re.compile(r'value|data|text|content|detail|info', re.I))
        
        for label_tag in label_tags:
            label = label_tag.get_text(strip=True).replace(':', '').strip()
            if not label or len(label) > 60:
                continue
                
            # Find value for this label
            parent = label_tag.find_parent()
            if parent:
                # Look for value in siblings or children
                for val_tag in parent.find_all(['p', 'span', 'div', 'strong']):
                    if val_tag != label_tag:
                        value = val_tag.get_text(strip=True)
                        if value and len(value) < 200:
                            all_data[label] = value
                            break

    # 4. Extract data from tables
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).replace(':', '').strip()
                value = cells[1].get_text(strip=True)
                if label and value:
                    all_data[label] = value

    # 5. Extract hidden data from attributes
    for element in soup.find_all(attrs={'data-': True}):
        for attr in element.attrs:
            if attr.startswith('data-'):
                key = attr.replace('data-', '').replace('-', ' ').title()
                value = element[attr]
                if key and value:
                    all_data[key] = value

    # 6. Extract from meta tags
    metas = soup.find_all('meta')
    for meta in metas:
        if meta.get('name') and meta.get('content'):
            all_data[meta['name']] = meta['content']
        if meta.get('property') and meta.get('content'):
            all_data[meta['property']] = meta['content']

    # 7. Extract owner name specifically (even with asterisks)
    owner_patterns = [
        r'[Oo]wner\s*[Nn]ame\s*[:：]\s*([^*\n]+)',
        r'[Oo]wner\s*[:：]\s*([^*\n]+)',
        r'[Nn]ame\s*[:：]\s*([^*\n]+)',
        r'[Aa]adhar\s*[Nn]ame\s*[:：]\s*([^*\n]+)',
        r'[Rr]egistered\s*[Oo]wner\s*[:：]\s*([^*\n]+)',
        r'[Rr]egistered\s*[Nn]ame\s*[:：]\s*([^*\n]+)',
    ]
    
    for pattern in owner_patterns:
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            owner = match.group(1).strip()
            if owner and len(owner) > 2:
                all_data['Owner Name'] = owner
                break

    # 8. Extract all text after keywords
    keywords = ['Owner', 'Name', 'Father', 'Address', 'Phone', 'Mobile', 'Email', 'Registration', 'RTO', 'Insurance', 'Model', 'Chassis', 'Engine']
    for keyword in keywords:
        pattern = rf'{keyword}.*?[:：]\s*([^*\n]+)'
        matches = re.findall(pattern, text_content, re.IGNORECASE)
        for match in matches:
            value = match.strip()
            if value and len(value) > 2:
                all_data[keyword] = value

    # 9. Extract from script tags (JSON data)
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            json_match = re.search(r'\{.*\}', script.string)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                    for key, value in json_data.items():
                        if isinstance(value, str) and len(value) > 1:
                            all_data[key] = value
                except:
                    pass

    # 10. Remove duplicates and clean
    cleaned_data = {}
    for key, value in all_data.items():
        # Clean the key
        clean_key = key.replace(':', '').strip()
        # Remove excessive whitespace
        clean_value = ' '.join(value.split())
        # Store if not empty
        if clean_key and clean_value:
            cleaned_data[clean_key] = clean_value

    return cleaned_data

def process_all_data(raw_data, rc):
    """Process and categorize ALL extracted data"""
    
    # Expanded key mappings with all possible variations
    key_map = {
        "Owner Details": [
            "Owner Name", "Owner", "Name", "Full Name", "Registered Owner", "R/O", "Owner's Name",
            "Father's Name", "Father Name", "F/H", "S/O", "D/O", "W/O", "Husband Name", "Spouse Name",
            "Mother's Name", "Guardian Name", "Owner Address", "Address", "Permanent Address",
            "City", "City Name", "District", "State", "Pin Code", "Pincode", "Zip Code",
            "Mobile", "Phone", "Contact", "Phone Number", "Mobile Number", "Email", "Email ID",
            "Aadhar", "Aadhar Number", "UID", "PAN", "PAN Number", "Voter ID", "Driving License"
        ],
        "Vehicle Details": [
            "Vehicle Model", "Model", "Model Name", "Model Number", "Vehicle Name", "Car Model",
            "Maker", "Manufacturer", "Make", "Brand", "Company", "Vehicle Class", "Class",
            "Fuel Type", "Fuel", "Fuel Norms", "Emission Norms", "BS", "BS Norms",
            "Chassis Number", "Chassis", "VIN", "Vehicle Identification Number",
            "Engine Number", "Engine", "Engine CC", "Cubic Capacity", "CC",
            "Seating Capacity", "Seats", "Capacity", "Vehicle Color", "Color", "Colour",
            "Manufacturing Year", "Year", "Model Year", "Vehicle Age", "Age",
            "Variant", "Trim", "Version", "Type", "Body Type", "Transmission", "Drive Type",
            "Fuel Capacity", "Tank Capacity", "Mileage", "Kilometer", "Odometer"
        ],
        "Registration Details": [
            "Registration Number", "RC Number", "Reg Number", "Vehicle Number", "License Plate",
            "RTO Code", "Registered RTO", "RTO", "Registration Date", "Reg Date", "Date of Reg",
            "Registration Authority", "Status", "Registration Status", "Active", "Validity",
            "Blacklist Status", "Blacklisted", "NOC", "NOC Details", "NOC Status",
            "Financer", "Financer Name", "Finance Company", "Loan Status", "Hypothecation"
        ],
        "Insurance Details": [
            "Insurance Company", "Insurer", "Insurance Provider", "Policy Provider",
            "Insurance Expiry", "Expiry Date", "Insurance Valid", "Valid Upto",
            "Insurance No", "Policy Number", "Insurance Policy Number",
            "Insurance Status", "Insurance Active", "Coverage Type", "Premium Amount",
            "Insurance Start", "Policy Start", "Insured Value", "Sum Insured"
        ],
        "Compliance Details": [
            "Fitness", "Fitness Upto", "Fitness Certificate", "FC",
            "PUC", "PUC Upto", "Pollution", "Emission Test",
            "PUC No", "Certificate Number",
            "Tax", "Road Tax", "Tax Upto", "Tax Paid", "Toll Tax",
            "Permit", "Permit Type", "Permit Validity", "National Permit", "State Permit",
            "Fitness Status", "Compliance Status", "Vehicle Inspection"
        ],
        "Owner Documents": [
            "Aadhar Number", "Aadhar", "UIDAI", "PAN Number", "PAN", 
            "Voter ID", "Driving License", "DL Number", "Passport",
            "Ration Card", "Gas Connection", "Bank Account", "IFSC Code"
        ]
    }

    structured_data = {
        "Owner Details": {},
        "Vehicle Details": {},
        "Registration Details": {},
        "Insurance Details": {},
        "Compliance Details": {},
        "Owner Documents": {},
        "Other Details": {}
    }

    # Process each data item
    for key, value in raw_data.items():
        clean_key = key.replace(':', '').strip()
        clean_value = ' '.join(value.split())
        
        if not clean_value or len(clean_key) > 60:
            continue
            
        # Skip common noise
        skip_patterns = ["Copyright", "Privacy", "Terms", "Cookies", "All Rights", "Contact Us", "About Us", "Login", "Sign Up"]
        if any(pattern in clean_key for pattern in skip_patterns):
            continue
        
        found = False
        
        # Try exact match first
        for category, keys_list in key_map.items():
            if clean_key in keys_list:
                structured_data[category][clean_key] = clean_value
                found = True
                break
        
        # Try partial match if not found
        if not found:
            for category, keys_list in key_map.items():
                for pattern_key in keys_list:
                    # Check if key contains pattern or vice versa
                    if (pattern_key.lower() in clean_key.lower() or 
                        clean_key.lower() in pattern_key.lower() or
                        clean_key.lower().replace(' ', '') == pattern_key.lower().replace(' ', '')):
                        structured_data[category][clean_key] = clean_value
                        found = True
                        break
                if found:
                    break
        
        # Special handling for numerical data (phone, aadhar, etc.)
        if not found and re.search(r'\d{10}', clean_value) and 'phone' in clean_key.lower():
            structured_data["Owner Details"]["Phone Number"] = clean_value
            found = True
        elif not found and re.search(r'\d{12}', clean_value) and 'aadhar' in clean_key.lower():
            structured_data["Owner Documents"]["Aadhar Number"] = clean_value
            found = True
        elif not found and re.search(r'[A-Z]{5}\d{4}[A-Z]', clean_value) and ('pan' in clean_key.lower() or 'pan' in clean_value.lower()):
            structured_data["Owner Documents"]["PAN Number"] = clean_value
            found = True
        
        # If still not found, put in Other Details
        if not found and clean_value and len(clean_key) < 60:
            structured_data["Other Details"][clean_key] = clean_value

    # Clean up empty categories
    final_data = {k: v for k, v in structured_data.items() if v}
    
    # Add metadata
    final_data["Registration Number"] = rc
    final_data["Developer Info"] = credits
    final_data["Data Count"] = sum(len(v) for v in structured_data.values())
    
    return final_data

def get_vehicle_details(rc_number):
    """Main function to get ALL vehicle details"""
    try:
        rc = rc_number.strip().upper()
        rc = rc.replace('=', '').replace('-', '').replace(' ', '')
        
        url = f"https://vahanx.in/rc-search/{rc}"
        headers = get_random_headers()
        
        try:
            response = requests.get(url, headers=headers, timeout=25)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract ALL data
            raw_data = extract_all_data(soup, rc)
            
            if raw_data:
                processed_data = process_all_data(raw_data, rc)
                processed_data["Source"] = "vahanx.in (Full Scrape)"
                return processed_data
            else:
                return {"status": "Partial", "message": "Limited data available", "rc": rc}
                
        except requests.exceptions.RequestException as e:
            return {"status": "Error", "message": f"Request failed: {str(e)}", "rc": rc}
            
    except Exception as e:
        return {"status": "Error", "message": f"Unexpected error: {str(e)}", "rc": rc}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/details=<path:rc_input>')
def api_fetch(rc_input):
    data = get_vehicle_details(rc_input)
    return Response(json.dumps(data, indent=4, ensure_ascii=False), mimetype='application/json')

@app.route('/ping')
def ping():
    return jsonify({"status": "alive", "version": "Ultimate Pro 3.0"})

if __name__ == "__main__":
    print("🚀 Ultimate Vehicle Info API Running")
    print("📍 http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
