#!/usr/bin/env python3
"""
财经看板生成器 - 获取所有标的价格并生成可视化HTML
"""
import json, time, subprocess
import urllib.request

TICKERS = {
    "A股": [
        {"symbol": "601899.SS", "name": "紫金矿业", "ticker": "601899", "unit": "¥"},
        {"symbol": "000001.SS", "name": "上证指数", "ticker": "000001", "unit": ""},
    ],
    "港股": [
        {"symbol": "1810.HK", "name": "小米集团", "ticker": "1810.HK", "unit": "HK$"},
    ],
    "美股": [
        {"symbol": "TSLA", "name": "Tesla", "ticker": "TSLA", "unit": "$"},
        {"symbol": "%5EIXIC", "name": "纳斯达克", "ticker": "^IXIC", "unit": ""},
    ],
    "加密": [
        {"symbol": "BTC-USD", "name": "Bitcoin", "ticker": "BTC", "unit": "$", "source": "coinbase"},
        {"symbol": "DOGE-USD", "name": "Dogecoin", "ticker": "DOGE", "unit": "$", "source": "coinbase"},
    ],
    "商品": [
        {"symbol": "GC%3DF", "name": "黄金", "ticker": "XAUUSD", "unit": "$"},
    ],
}

COINBASE_API = "https://api.coinbase.com/v2/prices/{}-USD/spot"

def fetch_yahoo(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    r2 = d["chart"]["result"][0]
    meta = r2["meta"]
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if not prev or not price:
        return None, None, None
    chg = round(price - prev, 2)
    pct = round(chg / prev * 100, 2)
    return price, chg, pct

def fetch_coinbase(ticker):
    url = COINBASE_API.format(ticker)
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read())
    price = float(d["data"]["amount"])
    # Coinbase doesn't give change, fetch previous close from Yahoo for base
    return price, None, None

def fetch_all():
    results = {}
    for category, items in TICKERS.items():
        results[category] = []
        for item in items:
            sym = item["symbol"]
            src = item.get("source", "yahoo")
            if src == "coinbase":
                price, chg, pct = fetch_coinbase(item["ticker"])
            else:
                price, chg, pct = fetch_yahoo(sym)
            results[category].append({
                "name": item["name"],
                "price": price,
                "change": chg,
                "pct": pct,
                "unit": item["unit"],
                "symbol": item["ticker"],
            })
            time.sleep(0.3)
    return results

def pct_bar(pct):
    """Generate a mini CSS bar for percentage"""
    width = min(abs(pct) * 3, 50) if pct else 0
    color = "#ef4444" if pct and pct < 0 else "#22c55e"
    return f'<div style="background:{color};width:{width}px;height:4px;border-radius:2px;margin-top:2px"></div>'

def build_html(data, update_time):
    # Color scheme
    bg = "#0a0e17"
    card_bg = "#111827"
    border = "#1f2937"
    text_primary = "#f9fafb"
    text_secondary = "#9ca3af"
    up_color = "#ef4444"   # A shares: red=up
    down_color = "#22c55e"  # A shares: green=down
    # For US stocks/crypto: green=up, red=down
    def change_color(pct, is_chinese=True):
        if pct is None: return text_secondary
        if is_chinese:
            return up_color if pct > 0 else down_color if pct < 0 else text_secondary
        else:
            return down_color if pct > 0 else up_color if pct < 0 else text_secondary

    def arrow(pct):
        if pct is None: return ""
        if pct > 0: return "▲"
        if pct < 0: return "▼"
        return "—"

    html_sections = ""
    for category, items in data.items():
        is_chinese = category in ("A股", "港股")
        cards_html = ""
        for item in items:
            pct = item["pct"]
            chg = item["change"]
            price = item["price"]
            unit = item["unit"]

            if pct is not None:
                pct_str = f"{arrow(pct)}{abs(pct)}%"
                chg_str = f"{arrow(pct)}{abs(chg)}" if chg is not None else ""
                pct_color = change_color(pct, is_chinese)
                bar = pct_bar(pct)
            else:
                pct_str = "—"
                chg_str = "—"
                pct_color = text_secondary
                bar = ""

            price_str = f"{unit}{price:,.2f}" if price else "—"

            cards_html += f"""
            <div class="asset-card">
                <div class="asset-name">{item['name']}</div>
                <div class="asset-symbol">{item['symbol']}</div>
                <div class="asset-price">{price_str}</div>
                <div class="asset-change" style="color:{pct_color}">
                    {chg_str} {pct_str}
                </div>
                {bar}
            </div>"""

        html_sections += f"""
        <div class="section">
            <div class="section-title">{category}</div>
            <div class="card-grid">{cards_html}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>财经看板</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: {bg}; color: {text_primary}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; padding: 20px; }}
  .header {{ text-align: center; padding: 16px 0 24px; }}
  .header h1 {{ font-size: 22px; font-weight: 600; letter-spacing: 2px; color: #e2e8f0; }}
  .header-time {{ font-size: 12px; color: #64748b; margin-top: 6px; }}
  .live-dot {{ display: inline-block; width: 6px; height: 6px; background: #22c55e; border-radius: 50%; margin-right: 4px; animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
  .grid {{ max-width: 600px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }}
  .section-title {{ font-size: 11px; letter-spacing: 2px; color: #475569; text-transform: uppercase; margin-bottom: 10px; padding-left: 4px; }}
  .card-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .asset-card {{
    background: {card_bg};
    border: 1px solid {border};
    border-radius: 12px;
    padding: 14px 16px;
  }}
  .asset-name {{ font-size: 14px; font-weight: 600; color: #e2e8f0; }}
  .asset-symbol {{ font-size: 10px; color: #475569; margin-top: 1px; margin-bottom: 8px; }}
  .asset-price {{ font-size: 18px; font-weight: 700; color: #f1f5f9; letter-spacing: -0.5px; }}
  .asset-change {{ font-size: 12px; font-weight: 500; margin-top: 4px; }}
  .footer {{ text-align: center; padding: 24px 0 8px; font-size: 11px; color: #334155; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 财经看板</h1>
  <div class="header-time"><span class="live-dot"></span>实时更新 · {update_time}</div>
</div>
<div class="grid">
{html_sections}
</div>
<div class="footer">数据来源: Yahoo Finance · Coinbase · 更新时间: {update_time}</div>
</body>
</html>"""
    return html

def main():
    print("Fetching all prices...")
    data = fetch_all()
    update_time = time.strftime("%Y-%m-%d %H:%M")
    html = build_html(data, update_time)

    out_path = "/Users/mateng/.openclaw/workspace/finance-tracker/index.html"
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Dashboard saved to {out_path}")

    # Git push (repo already initialized and remote configured)
    try:
        subprocess.run(["git", "add", "index.html"], cwd="/Users/mateng/.openclaw/workspace/finance-tracker", capture_output=True)
        commit_msg = f"Update dashboard {update_time}"
        result = subprocess.run(["git", "commit", "-m", commit_msg], cwd="/Users/mateng/.openclaw/workspace/finance-tracker", capture_output=True, text=True)
        if result.returncode == 0:
            subprocess.run(["git", "push", "origin", "main"], cwd="/Users/mateng/.openclaw/workspace/finance-tracker", timeout=30)
            print("Pushed to GitHub")
        else:
            print("Nothing to push (no changes)")
    except Exception as e:
        print(f"Git push error: {e}")

    # Print summary
    for cat, items in data.items():
        for item in items:
            print(f"  {item['name']}: {item['unit']}{item['price']} ({item['pct']}%)" if item['pct'] else f"  {item['name']}: {item['unit']}{item['price']}")

if __name__ == "__main__":
    main()
