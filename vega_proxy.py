from flask import Flask, jsonify, Response
from flask_cors import CORS
import requests
import threading
import time
import logging

app = Flask(__name__)
CORS(app)

# Since proxy and data server are on same AWS machine
GREEK_SERVER = "http://localhost:2000"

latest_data = ""
last_updated = ""
fetch_status = "starting"

logging.basicConfig(level=logging.INFO)

def fetch_loop():
    global latest_data, last_updated, fetch_status
    while True:
        try:
            r = requests.get(GREEK_SERVER, timeout=10)
            if r.status_code == 200:
                latest_data = r.text
                last_updated = time.strftime("%H:%M:%S")
                fetch_status = "ok"
                logging.info(f"Fetched OK at {last_updated}")
            else:
                fetch_status = f"http_{r.status_code}"
                logging.warning(f"Bad status: {r.status_code}")
        except Exception as e:
            fetch_status = f"error: {str(e)}"
            logging.error(f"Fetch error: {e}")
        time.sleep(58)

# Start background fetch thread
t = threading.Thread(target=fetch_loop, daemon=True)
t.start()

@app.route("/data")
def data():
    return Response(latest_data, mimetype="text/plain")

@app.route("/latest")
def latest():
    if not latest_data:
        return jsonify({"error": "no data yet"})
    lines = [l for l in latest_data.strip().split("\n") if l.strip()]
    return jsonify({
        "latest_row": lines[-1] if lines else "",
        "total_rows": len(lines),
        "last_updated": last_updated
    })

@app.route("/status")
def status():
    return jsonify({
        "status": fetch_status,
        "last_updated": last_updated,
        "data_server": GREEK_SERVER,
        "rows": len([l for l in latest_data.strip().split("\n") if l.strip()])
    })

@app.route("/")
def home():
    return f"""
    <h2>Vega Proxy — Running</h2>
    <p>Data server: {GREEK_SERVER}</p>
    <p>Last fetch: {last_updated}</p>
    <p>Status: {fetch_status}</p>
    <p>Endpoints: 
        <a href='/data'>/data</a> | 
        <a href='/latest'>/latest</a> | 
        <a href='/status'>/status</a>
    </p>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
