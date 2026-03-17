import os
import json
from datetime import datetime, timedelta
import yfinance as yf
import time

# -----------------------
# DATE
# -----------------------

today = datetime.now()
today_file = today.strftime("%Y%m%d")
today_str = today.strftime("%Y-%m-%d")

yesterday_file = (today - timedelta(days=1)).strftime("%Y%m%d")

DAILY_FILE = f"gold_rate_{today_file}.json"
OLD_FILE = f"gold_rate_{yesterday_file}.json"

# -----------------------
# YFINANCE FETCH
# -----------------------

# -----------------------
# RETRY HELPER
# -----------------------

def fetch_with_retry(ticker_symbol, name, retries=3, delay=5):
    for attempt in range(1, retries + 1):
        try:
            ticker = yf.Ticker(ticker_symbol)
            data = ticker.history(period="1d")

            if not data.empty:
                value = float(data["Close"].iloc[-1])
                print(f"✅ {name} fetched:", value)
                return value

            print(f"⚠ {name} empty (attempt {attempt})")

        except Exception as e:
            print(f"❌ {name} error (attempt {attempt}):", e)

        if attempt < retries:
            print(f"🔁 Retrying {name} in {delay} sec...")
            time.sleep(delay)

    print(f"❌ {name} failed after {retries} attempts")
    return None


# -----------------------
# YFINANCE FETCH
# -----------------------

def get_comex():
    return fetch_with_retry("GC=F", "COMEX")


def get_usdinr():
    return fetch_with_retry("INR=X", "USDINR")




# -----------------------
# IBJA (placeholder)
# -----------------------

def get_ibja():
    return None  # replace later


# -----------------------
# CALCULATE INR
# -----------------------

def calc_comex_inr(comex, usdinr):
    price_per_gram = (comex * usdinr) / 31.1035
    return round(price_per_gram)


# -----------------------
# LOAD OLD FILE (LOCAL)
# -----------------------

def load_old_file():
    if not os.path.exists(OLD_FILE):
        print("No old file found, starting fresh")
        return {"market": []}

    with open(OLD_FILE, "r") as f:
        return json.load(f)


# -----------------------
# MAIN
# -----------------------

def main():

    # ❌ Skip weekends
    if today.weekday() >= 5:
        print("⏸ Weekend - skipping update")
        return

    comex = get_comex()
    usdinr = get_usdinr()
    ibja = get_ibja()

    print("COMEX:", comex)
    print("USDINR:", usdinr)
    print("IBJA:", ibja)

    if not comex or not usdinr:
        print("❌ Failed to fetch COMEX/USDINR")
        return

    comex_per_gm = round(comex / 31.1035, 2)
    usdinr_val = round(usdinr, 2)
    comex_inr = calc_comex_inr(comex, usdinr)

    data = load_old_file()
    market = data.get("market", [])

    last = market[0] if market else None

    # ❌ Avoid duplicate same-day run
    if last and last["date"] == today_str:
        print("⚠ Already updated today")
        return

    # -----------------------
    # HOLIDAY DETECTION
    # -----------------------

    is_holiday = False

    if last:
        if (
            comex_per_gm == last.get("comex") and
            usdinr_val == last.get("usdinr")
        ):
            is_holiday = True

    # -----------------------
    # IBJA HANDLING
    # -----------------------

    if is_holiday:
        ibja_val = last.get("ibja999") if last else None
    else:
        ibja_val = ibja if ibja else (last.get("ibja999") if last else None)

    # -----------------------
    # NEW ROW
    # -----------------------

    new_data = {
        "date": today_str,
        "comex": comex_per_gm,
        "usdinr": usdinr_val,
        "comex_inr_999": comex_inr,
        "ibja999": ibja_val,
    }

    # remove duplicate date
    market = [m for m in market if m["date"] != today_str]

    # insert at top
    market.insert(0, new_data)

    # keep only 5 entries
    market = market[:5]

    # -----------------------
    # UPDATE ROOT
    # -----------------------

    data["market"] = market
    data["version"] = "2026V1"
    data["server_date"] = today_str
    data["updated"] = today.strftime("%Y-%m-%dT%H:%M:%S")

    # -----------------------
    # WRITE NEW FILE
    # -----------------------

    with open(DAILY_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print("✅ Created:", DAILY_FILE)

    # -----------------------
    # DELETE OLD FILE
    # -----------------------

    if os.path.exists(OLD_FILE):
        os.remove(OLD_FILE)
        print("🗑 Deleted:", OLD_FILE)

    print("✅ Done:", today_str)


# -----------------------

if __name__ == "__main__":
    main()