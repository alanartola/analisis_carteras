"""Retry/fill missing market caps using fast_info + shares outstanding, and
fall back to price * shares from get_shares_full where possible."""
import json
import time
import yfinance as yf

with open("scripts/market_caps_raw.json", encoding="utf-8") as f:
    results = json.load(f)

missing = [r for r in results if not r["market_cap"]]
print(f"{len(missing)} tickers missing market_cap: {[r['yf_ticker'] for r in missing]}")

for r in missing:
    yf_ticker = r["yf_ticker"]
    t = yf.Ticker(yf_ticker)
    cap = None
    price = r.get("price")
    currency = r.get("currency")
    try:
        fi = t.fast_info
        cap = fi.get("market_cap") if hasattr(fi, "get") else getattr(fi, "market_cap", None)
        if not price:
            price = fi.get("last_price") if hasattr(fi, "get") else getattr(fi, "last_price", None)
        if not currency:
            currency = fi.get("currency") if hasattr(fi, "get") else getattr(fi, "currency", None)
    except Exception as e:
        print(f"fast_info failed {yf_ticker}: {e}")
    if not cap:
        try:
            shares = t.get_shares_full(start="2026-06-01")
            if shares is not None and len(shares) and price:
                last_shares = shares.iloc[-1]
                cap = float(last_shares) * float(price)
        except Exception as e:
            print(f"shares_full failed {yf_ticker}: {e}")
    r["market_cap"] = cap
    r["price"] = price
    r["currency"] = currency
    print(f"{yf_ticker:10s} -> cap={cap} price={price} ccy={currency}")
    time.sleep(0.3)

with open("scripts/market_caps_raw.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

still_missing = [r["yf_ticker"] for r in results if not r["market_cap"]]
print(f"\nStill missing after retry: {still_missing}")
