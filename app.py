from flask import Flask, jsonify, Response, render_template, request
from flask_cors import CORS
import requests
import json
import re
from bs4 import BeautifulSoup
import time

app = Flask(__name__)
CORS(app)

credits = {
    'Developer': 'N.S',
    'Note': 'Data scraped from vahanx.in'
}

def get_vehicle_details(rc_number):
    """Fetch complete vehicle details from multiple sources"""
    rc = rc_number.strip().upper()
    rc = rc.replace('=', '').replace('-', '').replace(' ', '')
    
    # Try multiple approaches
    data = None
    
    # Approach 1: Try vahanx.in with better parsing
    data = try_vahanx(rc)
    if data and "error" not in data:
        return data
    
    # Approach 2: Try alternative source
    data = try_alternative_source(rc)
    if data and "error" not in data:
        return data
    
    # Approach 3: Return detailed error with suggestions
    return {
        "status": "Failed",
        "message": "Could not fetch vehicle details. Please try:",
        "suggestions": [
            "1. Check if RC number is correct (e.g., DL8CX1234)",
            "2. Try after a few minutes",
            "3. Contact support if issue persists"
        ],
        "rc_number": rc
    }

def try_vahanx(rc):
    """Try scraping from vahanx.in"""
    try:
        url = f"https://vahanx.in/rc-search/{rc}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Try to find the main data container
        data_container = soup.find("div", class_=re.compile(r"result|data|details|rc-details", re.I))
        
        if not data_container:
            # Try to find all divs that might contain data
            data_container = soup.find("div", class_=re.compile(r"container|main|content", re.I))
        
        raw_data = {}
        
        # Method 1: Find all span-p pairs
        all_spans = soup.find_all("span")
        for span in all_spans:
            label = span.get_text(strip=True)
            if not label or len(label) > 60 or "Copyright" in label:
                continue
            
            # Look for parent div or next sibling with value
            parent = span.find_parent()
            if parent:
                # Try to find value in a p tag within parent
                value_tag = parent.find("p")
                if value_tag:
                    value = value_tag.get_text(strip=True)
                else:
                    # Try to find value in a div or span after the label
                    next_elem = span.find_next_sibling()
                    if next_elem:
                        value = next_elem.get_text(strip=True)
                    else:
                        continue
                
                clean_key = label.replace(":", "").strip()
                if clean_key and value:
                    raw_data[clean_key] = value
        
        # Method 2: Find all divs with class containing 'item', 'row', etc.
        if not raw_data:
            divs = soup.find_all("div", class_=re.compile(r"item|row|field|detail", re.I))
            for div in divs:
                label_tag = div.find(["span", "label", "div"], class_=re.compile(r"label|key|title", re.I))
                value_tag = div.find(["span", "p", "div"], class_=re.compile(r"value|data|text", re.I))
                
                if label_tag and value_tag:
                    label = label_tag.get_text(strip=True).replace(":", "").strip()
                    value = value_tag.get_text(strip=True)
                    if label and value and len(label) < 50:
                        raw_data[label] = value
        
        # Process the extracted data
        if raw_data:
            return process_raw_data(raw_data, rc)
        else:
            return {"error": "No data found on vahanx.in"}
            
    except Exception as e:
        return {"error": f"vahanx.in error: {str(e)}"}

def try_alternative_source(rc):
    """Fallback to alternative data source"""
    try:
        # Try a different endpoint pattern
        urls = [
            f"https://vahanx.in/rc-search/{rc}?format=json",
            f"https://vahanx.in/rc-search/{rc}?type=full",
            f"https://vahanx.in/rc-search/{rc}?data=all"
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*"
        }
        
        for url in urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    # Try to parse JSON
                    try:
                        data = response.json()
                        if data and isinstance(data, dict):
                            return data
                    except:
                        pass
            except:
                continue
                
        return {"error": "Alternative sources failed"}
        
    except Exception as e:
        return {"error": f"Alternative error: {str(e)}"}

def process_raw_data(raw_data, rc):
    """Process and structure the raw scraped data"""
    structured_data = {
        "Owner Details": {},
        "Vehicle Details": {},
        "Registration Details": {},
        "Insurance Details": {},
        "Compliance Details": {},
        "Other Details": {}
    }

    key_map = {
        "Owner Details": ["Owner Name", "Father's Name", "Owner Serial No", "Email", "Address", "City Name", "Mobile", "Phone", "Contact"],
        "Vehicle Details": ["Model Name", "Maker Model", "Modal Name", "Vehicle Class", "Fuel Type", "Fuel Norms", "Chassis Number", "Engine Number", "Cubic Capacity", "Seating Capacity", "Vehicle Age", "Color", "Variant", "Manufacturing Year"],
        "Registration Details": ["Code", "Registration Number", "Registered RTO", "Registration Date", "Website", "Status", "Blacklist Status", "NOC Details", "Financer Name", "RTO Phone Number", "RTO Address"],
        "Insurance Details": ["Insurance Company", "Insurance Expiry", "Insurance Upto", "Insurance No", "Insurance Status", "Insurance Expiry In", "Policy Number"],
        "Compliance Details": ["Fitness Upto", "PUC Upto", "PUC No", "PUC Expiry In", "Tax Upto", "Permit Type", "Road Tax", "Emission Norms"]
    }

    for key, value in raw_data.items():
        # Clean up the key
        clean_key = key.replace(":", "").strip()
        
        # Skip unwanted data
        skip_patterns = ["Copyright", "2024", "2025", "Contact Us", "Privacy", "Terms"]
        if any(pattern in clean_key for pattern in skip_patterns):
            continue
            
        found = False
        
        # Special handling for phone numbers
        if "phone" in clean_key.lower() or "mobile" in clean_key.lower() or "contact" in clean_key.lower():
            structured_data["Owner Details"]["Phone"] = value
            continue
            
        # Categorize the data
        for category, keys_list in key_map.items():
            if clean_key in keys_list:
                structured_data[category][clean_key] = value
                found = True
                break
        
        # Check if value matches any key pattern
        if not found:
            for category, keys_list in key_map.items():
                for pattern_key in keys_list:
                    if pattern_key.lower() in clean_key.lower() or clean_key.lower() in pattern_key.lower():
                        structured_data[category][clean_key] = value
                        found = True
                        break
                if found:
                    break
        
        # If still not found, put in Other Details
        if not found and value and len(clean_key) < 50:
            structured_data["Other Details"][clean_key] = value

    # Clean up empty categories
    final_data = {k: v for k, v in structured_data.items() if v}
    final_data["Registration Number"] = rc
    final_data["Developer Info"] = credits
    final_data["Status"] = "Data retrieved successfully"
    
    return final_data

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/details=<path:rc_input>')
def api_fetch(rc_input):
    data = get_vehicle_details(rc_input)
    return Response(json.dumps(data, indent=4, ensure_ascii=False), mimetype='application/json')

@app.route('/ping')
def ping():
    return jsonify({"status": "alive", "message": "Server is running!"})

if __name__ == "__main__":
    print("Server running on http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080)
