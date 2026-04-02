from flask import Flask, render_template, jsonify, request
import os
import time
import threading
import requests

# ================== APP SETUP ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

# ================== CONFIG ==================
CACHE_TTL = 10
UPDATE_INTERVAL = 20

# ================== SYMBOLS ==================
SYMBOLS = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN",
    "KOTAKBANK","AXISBANK","INDUSINDBK","WIPRO","HCLTECH","TECHM"
]

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

# ================== SESSION ==================
session = requests.Session()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}

def init_session():
    try:
        session.get("https://www.nseindia.com", headers=HEADERS, timeout=5)
    except:
        pass

# ================== FETCH CANDLES ==================
def fetch_candles(symbol):
    try:
        url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}"
        res = session.get(url, headers=HEADERS, timeout=5)

        if res.status_code != 200:
            return []

        data = res.json()

        timestamps = data.get("grapthData", [])

        candles = []

        # Convert tick data → OHLC (1m grouping)
        bucket = []

        current_min = None

        for ts, price in timestamps:
            minute = int(ts // 60000)

            if current_min is None:
                current_min = minute

            if minute != current_min:
                if bucket:
                    candles.append({
                        "time": bucket[0][0],
                        "open": bucket[0][1],
                        "high": max(x[1] for x in bucket),
                        "low": min(x[1] for x in bucket),
                        "close": bucket[-1][1],
                        "volume": 0
                    })
                bucket = []
                current_min = minute

            bucket.append((ts, price))

        return candles

    except Exception as e:
        print(symbol, "error:", e)
        return []

# ================== BACKGROUND LOOP ==================
def update_loop():
    init_session()

    while True:
        for symbol in SYMBOLS:
            try:
                time.sleep(0.5)  # prevent blocking

                candles = fetch_candles(symbol)
                if candles:
                    set_cache(symbol, candles)

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
    return jsonify([{"symbol": s, "name": s} for s in SYMBOLS])

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
