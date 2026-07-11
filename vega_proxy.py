from flask import Flask, Response, request, send_from_directory, jsonify
from flask_cors import CORS
import requests, threading, time, logging, json
import os

app = Flask(__name__)
CORS(app)

GREEK_SERVER = "http://localhost:2000"

latest_data = ""
last_updated = ""
fetch_status = "idle"
current_payload = None

logging.basicConfig(level=logging.INFO)

def json_to_tsv(raw_text):
    # Convert port 2000 JSON array-of-arrays into tab-separated text, oldest first
    try:
        arr = json.loads(raw_text)
        if not isinstance(arr, list):
            return raw_text
        rows = []
        for row in arr:
            # row[0]=time, row[1..12]=12 greek values, row[13]=duplicate time -> drop it
            cells = row[:13] if len(row) > 13 else row
            rows.append("\t".join(str(c) for c in cells))
        # API is newest-first; dashboard wants oldest-first
        rows.reverse()
        return "\n".join(rows)
    except Exception as e:
        logging.error(f"json_to_tsv failed: {e}")
        return raw_text

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
        logging.info(f"Default payload built: BN={len(bn)} NF={len(nf)} strikes=5")
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
            latest_data = json_to_tsv(r.text)
            last_updated = time.strftime("%H:%M:%S")
            fetch_status = "ok"
            logging.info(f"Fetched OK at {last_updated}, {latest_data.count(chr(10))+1} rows")
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


SIGNAL_DIR = r'C:\vega'

@app.route('/logsignal', methods=['POST'])
def logsignal():
    try:
        sig = request.get_json(force=True, silent=True) or {}
        t = sig.get('time', '')
        line = sig.get('line', '')
        if not t:
            return jsonify({"ok": False, "err": "no time"}), 400
        fname = os.path.join(SIGNAL_DIR, "signals_" + time.strftime("%Y-%m-%d") + ".txt")
        existing = set()
        if os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8') as f:
                for ln in f:
                    if '\t' in ln:
                        existing.add(ln.split('\t', 1)[0])
        if t in existing:
            return jsonify({"ok": True, "dup": True})
        with open(fname, 'a', encoding='utf-8') as f:
            f.write(t + '\t' + line.replace('\n', ' ') + '\n')
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

@app.route('/log')
def viewlog():
    try:
        fname = os.path.join(SIGNAL_DIR, "signals_" + time.strftime("%Y-%m-%d") + ".txt")
        rows = ""
        if os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8') as f:
                for ln in f:
                    if '\t' in ln:
                        t, d = ln.rstrip('\n').split('\t', 1)
                        rows += "<tr><td style='padding:6px 12px;white-space:nowrap;color:#0288a8;font-weight:bold'>" + t + "</td><td style='padding:6px 12px'>" + d + "</td></tr>"
        if not rows:
            rows = "<tr><td colspan='2' style='padding:20px;text-align:center;color:#5a6b7e'>No signals logged yet today</td></tr>"
        html = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><title>Signal Log</title></head><body style='font-family:monospace;background:#f4f6f9;color:#14202e;margin:0;padding:16px'><h2 style='color:#0288a8'>VEGA LIVE - Signal Log " + time.strftime("%Y-%m-%d") + "</h2><table style='border-collapse:collapse;width:100%;background:#fff;border:1px solid #c5d0dd'>" + rows + "</table><p style='margin-top:12px'><a href='/' style='color:#0288a8'>back to dashboard</a></p></body></html>"
        return Response(html, mimetype='text/html')
    except Exception as e:
        return Response("error: " + str(e), mimetype='text/plain')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

