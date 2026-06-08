from flask import Flask, Response, send_from_directory
from flask_cors import CORS
import requests, threading, time, logging

app = Flask(__name__)
CORS(app)

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
        except Exception as e:
            fetch_status = f"error: {str(e)}"
            logging.error(f"Fetch error: {e}")
        time.sleep(58)

t = threading.Thread(target=fetch_loop, daemon=True)
t.start()

@app.route('/')
def index():
    return send_from_directory(r'C:\vega', 'index.html')

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
    return f"<h2>Vega Proxy &#8212; Running</h2><p>Data server: {GREEK_SERVER}</p><p>Last fetch: {last_updated}</p><p>Status: {fetch_status}</p><p>Endpoints: <a href='/data'>/data</a> | <a href='/latest'>/latest</a> | <a href='/status'>/status</a></p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
