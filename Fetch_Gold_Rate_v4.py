import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import yfinance as yf
import time

# -----------------------
# DATE (IST)
# -----------------------

IST = ZoneInfo("Asia/Kolkata")
now_ist = datetime.now(IST)

today = now_ist
today_file = today.strftime("%Y%m%d")
today_str = today.strftime("%Y-%m-%d")

is_post_11am = now_ist.hour >= 11

yesterday_file = (today - timedelta(days=1)).strftime("%Y%m%d")

DAILY_FILE = f"gold_rate_{today_file}.json"
OLD_FILE = f"gold_rate_{yesterday_file}.json"

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
# CALCULATIONS
# -----------------------

def calculate_final_india_rate(comex, usdinr, mcx):

    comex_base = (comex * usdinr) / 31.1035
    comex_adjusted = comex_base * 1.125 * 1.025 * 1.03 * 1.005

    if mcx:
        mcx_per_g = mcx / 10
        mcx_retail = mcx_per_g * 1.004 * 1.03 * 1.006

        diff = abs(mcx_retail - comex_adjusted) / comex_adjusted

        weight_mcx = 0.5 if diff > 0.02 else 0.3

        final_price = (
            comex_adjusted * (1 - weight_mcx)
            + mcx_retail * weight_mcx
        )
    else:
        final_price = comex_adjusted

    return round(final_price, 2), round(final_price * 10, 2)


def calc_comex_inr(comex, usdinr):
    price_per_gram = (comex * usdinr) / 31.1035
    return round(price_per_gram)


# -----------------------
# LOAD OLD FILE
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

    if not comex or not usdinr:
        print("❌ Failed to fetch COMEX/USDINR")
        return

    india_rate_999, _ = calculate_final_india_rate(comex, usdinr, None)

    print("COMEX:", comex)
    print("USDINR:", usdinr)
    print("India Ref Rate:", india_rate_999)

    comex_per_gm = round(comex / 31.1035, 2)
    usdinr_val = round(usdinr, 2)
    comex_inr = calc_comex_inr(comex, usdinr)

    data = load_old_file()
    market = data.get("market", [])

    last = market[0] if market else None

    # -----------------------
    # DETERMINE SLOT
    # -----------------------

    slot = "post_11am" if is_post_11am else "morning"

    # -----------------------
    # FIND / CREATE TODAY ENTRY
    # -----------------------

    if last and last["date"] == today_str:
        today_entry = last
        print(f"🔄 Updating {slot}")
    else:
        today_entry = {
            "date": today_str,
            "morning": None,
            "post_11am": None
        }
        print("🆕 Creating new entry")

    # -----------------------
    # HOLIDAY DETECTION
    # -----------------------

    is_holiday = False

    if last and last.get("morning"):
        prev = last["morning"]
        if (
            comex_per_gm == prev.get("comex") and
            usdinr_val == prev.get("usdinr")
        ):
            is_holiday = True

    # -----------------------
    # INDIA RATE HANDLING
    # -----------------------

    if is_holiday and today_entry.get(slot):
        india_rate_999_val = today_entry[slot].get("india_rate_999")
    else:
        india_rate_999_val = india_rate_999

    # -----------------------
    # SLOT DATA
    # -----------------------

    slot_data = {
        "updated": now_ist.strftime("%Y-%m-%dT%H:%M:%S"),
        "comex": comex_per_gm,
        "usdinr": usdinr_val,
        "comex_inr_999": comex_inr,
        "india_rate_999": india_rate_999_val,
    }

    today_entry[slot] = slot_data

    # -----------------------
    # UPDATE MARKET LIST
    # -----------------------

    market = [m for m in market if m["date"] != today_str]
    market.insert(0, today_entry)
    market = market[:5]

    # -----------------------
    # ROOT UPDATE
    # -----------------------

    data["version"] = "2026V1"
    data["server_date"] = today_str
    data["updated"] = now_ist.strftime("%Y-%m-%dT%H:%M:%S")
    data["market"] = market

    # -----------------------
    # WRITE FILE
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