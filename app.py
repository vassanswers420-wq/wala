from flask import Flask, render_template, jsonify, request
import os
import time
import threading
import requests

# ================== APP SETUP ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

# ================== CONFIG ==================
CACHE_TTL = 15
UPDATE_INTERVAL = 60

# ================== SYMBOL MAP ==================
# NSE → Stooq format (limited coverage)
SYMBOL_MAP = {
    "RELIANCE": "reliance.in",
    "TCS": "tcs.in",
    "INFY": "infy.in",
    "HDFCBANK": "hdfcbank.in",
    "ICICIBANK": "icicibank.in",
    "SBIN": "sbin.in"
}

# ================== CACHE ==================
cache = {}

def get_cached(symbol):
    now = time.time()
    if symbol in cache:
        ts, data = cache[symbol]
        if now - ts < CACHE_TTL:
            return data
    return None

def set_cache(symbol, data):
    cache[symbol] = (time.time(), data)

# ================== FETCH DATA ==================
def fetch_symbol(symbol):
    try:
        stooq_symbol = SYMBOL_MAP.get(symbol)
        if not stooq_symbol:
            return []

        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=1"
        res = requests.get(url, timeout=5)

        if res.status_code != 200:
            return []

        lines = res.text.split("\n")
        candles = []

        # skip header
        for line in lines[1:]:
            if not line.strip():
                continue

            parts = line.split(",")
            if len(parts) < 6:
                continue

            # date,time,open,high,low,close,volume
            ts = parts[0] + " " + parts[1]

            candles.append({
                "time": int(time.time() * 1000),  # fallback time
                "open": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "close": float(parts[5]),
                "volume": int(parts[6]) if len(parts) > 6 else 0
            })

        return candles[-200:]  # last 200 candles

    except Exception as e:
        print(symbol, "error:", e)
        return []

# ================== BACKGROUND LOOP ==================
def update_loop():
    while True:
        for symbol in SYMBOL_MAP.keys():
            try:
                time.sleep(1)
                data = fetch_symbol(symbol)
                if data:
                    set_cache(symbol, data)
            except Exception as e:
                print(symbol, "update error:", e)

        time.sleep(UPDATE_INTERVAL)

@app.before_first_request
def start_background_thread():
    threading.Thread(target=update_loop, daemon=True).start()

# ================== ROUTES ==================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/symbols')
def get_symbols():
    return jsonify([{"symbol": s, "name": s} for s in SYMBOL_MAP.keys()])

@app.route('/api/data')
def get_symbol_data():
    symbol = request.args.get('symbol', '').upper()

    if not symbol:
        return jsonify({"error": "Symbol required"}), 400

    cached = get_cached(symbol)
    if cached:
        return jsonify(cached)

    return jsonify([])

# ================== START ==================
if __name__ == "__main__":
    app.run(debug=True)
