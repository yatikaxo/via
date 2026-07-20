from flask import Flask, jsonify, Response, render_template, request
from flask_cors import CORS
import requests
import json
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
CORS(app)

credits = {
    'Telegram': "@modsnew || @HUNTER_X_OSINT",
    'Developer': '@NuxoFF And @SHURU_33'
}

def get_vehicle_details(rc_number):
    rc = rc_number.strip().upper()
    rc = rc.replace('=', '')
    
    url = f"https://vahanx.in/rc-search/{rc}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {e}"}

    raw_data = {}
    all_spans = soup.find_all("span")
    for span in all_spans:
        label = span.get_text(strip=True)
        if not label or len(label) > 60 or "Copyright" in label:
            continue
        parent_div = span.find_parent("div")
        if parent_div:
            value_tag = parent_div.find("p")
            if value_tag:
                value = value_tag.get_text(strip=True)
                clean_key = label.replace(":", "").strip()
                if clean_key in ["2024"]:
                    continue
                if clean_key in ["Insurance Valid Upto", "If your insurance has expired, renew it"]:
                    clean_key = "Insurance Status"
                if clean_key and value:
                    raw_data[clean_key] = value

    if not raw_data:
        return {"status": "Failed", "message": "No details found or invalid RC number."}

    structured_data = {
        "Owner Details": {},
        "Vehicle Details": {},
        "Registration Details": {},
        "Insurance Details": {},
        "Compliance Details": {},
        "Other Details": {}
    }

    key_map = {
        "Owner Details": ["Owner Name", "Father's Name", "Owner Serial No", "Email", "Address", "City Name"],
        "Vehicle Details": ["Model Name", "Maker Model", "Modal Name", "Vehicle Class", "Fuel Type", "Fuel Norms", "Chassis Number", "Engine Number", "Cubic Capacity", "Seating Capacity", "Vehicle Age", "Color"],
        "Registration Details": ["Code", "Registration Number", "Registered RTO", "Registration Date", "Website", "Status", "Blacklist Status", "NOC Details", "Financer Name"],
        "Insurance Details": ["Insurance Company", "Insurance Expiry", "Insurance Upto", "Insurance No", "Insurance Status", "Insurance Expiry In"],
        "Compliance Details": ["Fitness Upto", "PUC Upto", "PUC No", "PUC Expiry In", "Tax Upto", "Permit Type"]
    }

    for key, value in raw_data.items():
        found = False
        if key == "Phone":
            structured_data["Registration Details"]["RTO Phone Number"] = value
        else:
            for category, keys_list in key_map.items():
                if key in keys_list:
                    structured_data[category][key] = value
                    found = True
                    break
            if not found:
                structured_data["Other Details"][key] = value

    if "Registration Details" in structured_data and "RTO Phone Number" in structured_data["Registration Details"]:
        reg = structured_data["Registration Details"]
        ordered_keys = []
        for k in key_map["Registration Details"]:
            if k in reg:
                ordered_keys.append(k)
        if "RTO Phone Number" in reg:
            if "Registration Date" in ordered_keys:
                idx = ordered_keys.index("Registration Date") + 1
                ordered_keys.insert(idx, "RTO Phone Number")
            else:
                ordered_keys.append("RTO Phone Number")
        for k in reg:
            if k not in ordered_keys:
                ordered_keys.append(k)
        structured_data["Registration Details"] = {k: reg[k] for k in ordered_keys}

    final_data = {k: v for k, v in structured_data.items() if v}
    final_data["Developer Info"] = credits
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
    return jsonify({"status": "alive"})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    print(f"Server running on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)