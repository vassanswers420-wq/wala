from flask import Flask, render_template, jsonify, request
import os
import yfinance as yf
import time
import threading

# ================== APP SETUP ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

# ================== CONFIG ==================
CACHE_TTL = 15       # seconds
UPDATE_INTERVAL = 60 # 🔥 IMPORTANT (was 5)

# ================== SYMBOLS ==================
SYMBOLS = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN",
    "KOTAKBANK","AXISBANK","INDUSINDBK","WIPRO","HCLTECH","TECHM",
    "ONGC","BPCL","IOC","POWERGRID","NTPC","ITC","HINDUNILVR",
    "NESTLEIND","BRITANNIA","DABUR","MARICO","MARUTI","TATAMOTORS",
    "M&M","BAJAJ-AUTO","HEROMOTOCO","EICHERMOT","SUNPHARMA",
    "DRREDDY","CIPLA","DIVISLAB","LUPIN","TATASTEEL","JSWSTEEL",
    "HINDALCO","COALINDIA","VEDL","LT","ULTRACEMCO","ASIANPAINT",
    "BAJFINANCE","BAJAJFINSV","ADANIENT","ADANIPORTS","GRASIM",
    "SHREECEM","APOLLOHOSP"
]

# ================== CACHE ==================
cache = {}  # {symbol: (timestamp, data)}

def get_cached(symbol):
    now = time.time()
    if symbol in cache:
        ts, data = cache[symbol]
        if now - ts < CACHE_TTL:
            return data
    return None

def set_cache(symbol, data):
    cache[symbol] = (time.time(), data)

# ================== BATCH FETCH ==================
def fetch_all_symbols():
    try:
        tickers = " ".join([f"{s}.NS" for s in SYMBOLS])

        data = yf.download(
            tickers=tickers,
            interval="1m",
            period="1d",
            group_by="ticker",
            threads=False  # 🔥 CRITICAL
        )

        for symbol in SYMBOLS:
            try:
                df = data[symbol + ".NS"]

                if df.empty:
                    continue

                ohlc = []
                for t, row in df.iterrows():
                    ohlc.append({
                        "time": int(t.timestamp() * 1000),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"])
                    })

                set_cache(symbol, ohlc)

            except Exception as e:
                print(f"{symbol} parse error:", e)

    except Exception as e:
        print("Batch fetch failed:", e)

# ================== BACKGROUND LOOP ==================
def update_loop():
    while True:
        fetch_all_symbols()
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

    # fallback if not cached yet
    return jsonify([])

# ================== START ==================
if __name__ == "__main__":
    app.run(debug=True)
