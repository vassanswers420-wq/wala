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
from datetime import datetime

def fetch_symbol(symbol):
    try:
        stooq_symbol = SYMBOL_MAP.get(symbol)
        if not stooq_symbol:
            return []

        # Try intraday first
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=1"
        res = requests.get(url, timeout=5)

        if res.status_code != 200 or "No data" in res.text:
            return []

        lines = res.text.strip().split("\n")
        candles = []

        for line in lines[1:]:  # skip header
            parts = line.split(",")

            if len(parts) < 6:
                continue

            try:
                # ✅ FIXED TIME PARSING
                dt_str = parts[0] + " " + parts[1]
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                timestamp = int(dt.timestamp() * 1000)

                candles.append({
                    "time": timestamp,
                    "open": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "close": float(parts[5]),
                    "volume": int(parts[6]) if len(parts) > 6 else 0
                })

            except Exception:
                continue

        # 🔥 FALLBACK: if intraday empty → try daily
        if not candles:
            url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
            res = requests.get(url, timeout=5)

            lines = res.text.strip().split("\n")

            for line in lines[1:]:
                parts = line.split(",")

                if len(parts) < 5:
                    continue

                try:
                    dt = datetime.strptime(parts[0], "%Y-%m-%d")
                    timestamp = int(dt.timestamp() * 1000)

                    candles.append({
                        "time": timestamp,
                        "open": float(parts[1]),
                        "high": float(parts[2]),
                        "low": float(parts[3]),
                        "close": float(parts[4]),
                        "volume": int(parts[5]) if len(parts) > 5 else 0
                    })

                except:
                    continue

        return candles[-200:]

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

    # 🔥 FETCH IF NOT IN CACHE
    data = fetch_symbol(symbol)

    if data:
        set_cache(symbol, data)
        return jsonify(data)

    return jsonify({"error": "No data available"})
# ================== START ==================
if __name__ == "__main__":
    app.run(debug=True)
