from flask import Flask, Response, request, send_from_directory, jsonify
from flask_cors import CORS
import requests, threading, time, logging

app = Flask(__name__)
CORS(app)

GREEK_SERVER = "http://localhost:2000"

latest_data = ""
last_updated = ""
fetch_status = "idle"
current_payload = None

logging.basicConfig(level=logging.INFO)

def build_default_payload():
    try:
        r = requests.get(GREEK_SERVER + "/config", timeout=15)
        cfg = r.json()
        exp = cfg.get("expiries", {})
        bn = exp.get("BANKNIFTY", [])
        nf = exp.get("NIFTY", [])
        payload = {
            "BANKNIFTY": {"expiries": bn, "strikes": 5},
            "NIFTY": {"expiries": nf, "strikes": 5}
        }
        logging.info(f"Default payload built: BN={len(bn)} expiries, NF={len(nf)} expiries, strikes=5")
        return payload
    except Exception as e:
        logging.error(f"Could not build default payload: {e}")
        return None

def do_fetch():
    global latest_data, last_updated, fetch_status
    if not current_payload:
        return
    try:
        r = requests.post(GREEK_SERVER + "/data", json=current_payload, timeout=20)
        if r.status_code == 200:
            latest_data = r.text
            last_updated = time.strftime("%H:%M:%S")
            fetch_status = "ok"
            logging.info(f"Fetched OK at {last_updated}")
        else:
            fetch_status = f"http_{r.status_code}"
    except Exception as e:
        fetch_status = f"error: {str(e)}"

def startup_init():
    global current_payload
    for attempt in range(12):
        p = build_default_payload()
        if p:
            current_payload = p
            do_fetch()
            return
        time.sleep(10)

def fetch_loop():
    while True:
        if current_payload:
            do_fetch()
        time.sleep(58)

threading.Thread(target=startup_init, daemon=True).start()
threading.Thread(target=fetch_loop, daemon=True).start()

@app.route('/')
def index():
    return send_from_directory(r'C:\vega', 'index.html')

@app.route('/config')
def config():
    try:
        r = requests.get(GREEK_SERVER + "/config", timeout=15)
        return Response(r.text, mimetype='application/json', status=r.status_code)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.route('/fetch', methods=['POST'])
def fetch():
    global current_payload
    current_payload = request.get_json(force=True, silent=True)
    do_fetch()
    return jsonify({"status": fetch_status, "last_updated": last_updated})

@app.route('/data')
def data():
    return Response(latest_data, mimetype='text/plain')

@app.route('/latest')
def latest():
    if not latest_data:
        return Response('', mimetype='text/plain')
    lines = latest_data.strip().split('\n')
    return Response(lines[-1] if lines else '', mimetype='text/plain')

@app.route('/status')
def status():
    return jsonify({"data_server": GREEK_SERVER, "last_updated": last_updated, "status": fetch_status})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
