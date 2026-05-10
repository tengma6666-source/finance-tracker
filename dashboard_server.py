#!/usr/bin/env python3
"""
Finance Tracker Dashboard Server — LaunchAgent 版本
端口 8766，后台线程定时刷新数据，页面无阻塞
"""
import http.server
import socketserver
import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from threading import Thread
import time

PORT = 8766
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# ---------- 缓存数据 ----------
cached_data = {}
cache_time = 0
CACHE_TTL = 300  # 5分钟刷新一次

tickers = {
    "A股": [
        ("紫金矿业", "601899.SS", "¥"),
        ("航天电子", "600879.SS", "¥"),
        ("上证指数", "000001.SS", ""),
    ],
    "港股": [
        ("小米集团", "1810.HK", "HK$"),
    ],
    "美股": [
        ("Tesla", "TSLA", "$"),
        ("纳斯达克", "^IXIC", ""),
    ],
    "加密": [
        ("Bitcoin", "BTC-USD", "$"),
        ("Dogecoin", "DOGE-USD", "$"),
    ],
    "商品": [
        ("黄金", "GC=F", "$"),
    ],
}

cat_icons = {"A股": "🏛", "港股": "🇭🇰", "美股": "🇺🇸", "加密": "₿", "商品": "🪙"}

def fetch_one(name, symbol, unit):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice", 0) or meta.get("previousClose", 0)
        prev = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        change = price - prev
        pct = (change / prev * 100) if prev else 0
        return name, {"price": price, "change": change, "pct": pct, "unit": unit, "symbol": symbol}
    except Exception as e:
        return name, {"price": 0, "change": 0, "pct": 0, "unit": unit, "symbol": symbol, "error": str(e)}

def refresh_data():
    global cached_data, cache_time
    results = {}
    threads = []
    for cat, items in tickers.items():
        results[cat] = []
        for name, symbol, unit in items:
            def worker(n=sname, s=sym, u=uni):
                return fetch_one(n, s, u)
            # capture correctly
            pass
        for name, symbol, unit in items:
            t = Thread(target=lambda n, s, u: results.update([fetch_one(n, s, u)]), args=(name, symbol, unit))
            t.start()
            threads.append(t)
    for t in threads:
        t.join(timeout=8)
    # rebuild per-category dict
    final = {}
    for cat, items in tickers.items():
        final[cat] = []
        for name, _, _ in items:
            if name in cached_data:
                final[cat].append(cached_data[name])
    cached_data = final
    cache_time = time.time()

def refresh_data_simple():
    """简单顺序fetch，无线程，简单可靠"""
    global cached_data, cache_time
    results = {}
    for cat, items in tickers.items():
        results[cat] = []
        for name, symbol, unit in items:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                r = data["chart"]["result"][0]["meta"]
                price = r.get("regularMarketPrice") or r.get("previousClose", 0)
                prev = r.get("chartPreviousClose") or r.get("previousClose", price)
                change = price - prev
                pct = (change / prev * 100) if prev else 0
                results[cat].append({"name": name, "price": price, "change": change, "pct": pct, "unit": unit, "symbol": symbol})
                time.sleep(0.15)
            except Exception as e:
                results[cat].append({"name": name, "price": 0, "change": 0, "pct": 0, "unit": unit, "symbol": symbol})
    cached_data = results
    cache_time = time.time()

def fmt_price(price, unit):
    if unit == "¥":
        return f"¥{price:.2f}"
    elif unit == "HK$":
        return f"HK${price:.2f}"
    elif unit == "$":
        if price < 1:
            return f"${price:.4f}"
        return f"${price:,.2f}"
    return f"{price:,.2f}"

def bar_width(pct):
    return min(abs(pct) * 12, 120)

def build_html():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    age = int(time.time() - cache_time) if cache_time else 0

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>财经看板</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0d1117; color: #e6edf3; font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; min-height: 100vh; padding: 24px 16px 40px; }}
.header {{ text-align: center; margin-bottom: 28px; }}
.header h1 {{ font-size: 20px; font-weight: 700; letter-spacing: 3px; background: linear-gradient(90deg, #33B5E7, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.header .time {{ font-size: 11px; color: #484f58; margin-top: 6px; letter-spacing: 1px; }}
.section {{ margin-bottom: 28px; }}
.section-label {{ display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding-left: 4px; }}
.section-label span {{ font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #484f58; }}
.section-label .line {{ flex: 1; height: 1px; background: linear-gradient(90deg, #21262d, transparent); }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px; }}
.card {{ background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 14px 16px; position: relative; overflow: hidden; transition: border-color 0.2s; }}
.card:hover {{ border-color: #30363d; }}
.card::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; }}
.up::before {{ background: linear-gradient(90deg, #f97316, #fb923c); }}
.up .pct-wrap {{ color: #f97316; }}
.down::before {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
.down .pct-wrap {{ color: #3b82f6; }}
.flat::before {{ background: #30363d; }}
.flat .pct-wrap {{ color: #484f58; }}
.card-top {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
.card-name {{ font-size: 13px; font-weight: 600; color: #8b949e; }}
.card-sym {{ font-size: 10px; color: #30363d; letter-spacing: 1px; }}
.pct-wrap {{ font-size: 12px; font-weight: 700; white-space: nowrap; }}
.card-price {{ font-size: 20px; font-weight: 700; color: #e6edf3; margin-bottom: 8px; letter-spacing: -0.5px; }}
.bar-bg {{ height: 4px; background: #21262d; border-radius: 2px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 2px; }}
.up .bar-fill {{ background: linear-gradient(90deg, #f97316, #fbbf24); }}
.down .bar-fill {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
.flat .bar-fill {{ background: #30363d; }}
.chg-row {{ display: flex; justify-content: space-between; margin-top: 6px; font-size: 10px; color: #484f58; }}
.footer {{ text-align: center; margin-top: 32px; font-size: 10px; color: #30363d; letter-spacing: 1px; }}
@keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
.live {{ display:inline-block; width:6px; height:6px; background:#22c55e; border-radius:50%; animation:pulse 2s infinite; margin-right:4px; }}
</style>
</head>
<body>
<div class="header">
    <h1>📊 小马哥的财经看板</h1>
    <div class="time"><span class="live"></span>实时 · {now} · {age}s前刷新</div>
</div>
"""

    for cat, items in cached_data.items():
        icon = cat_icons.get(cat, "")
        html += f'<div class="section">\n  <div class="section-label"><span>{icon} {cat}</span><div class="line"></div></div>\n  <div class="cards">\n'
        for item in items:
            pct = item.get("pct", 0)
            chg = item.get("change", 0)
            up = pct > 0.001
            down = pct < -0.001
            cls = "up" if up else ("down" if down else "flat")
            arrow = "▲" if up else ("▼" if down else "—")
            sign = "+" if not down else ""
            price_str = fmt_price(item.get("price", 0), item.get("unit", ""))
            bar_w = bar_width(pct) if pct else 0
            pct_str = f"{sign}{pct:.2f}%"
            chg_unit = item.get("unit", "$")
            chg_disp = f"{chg_unit}{abs(float(chg)):.2f}" if chg_unit else f"${abs(float(chg)):.2f}"
            html += f"""  <div class="card {cls}">
    <div class="card-top">
      <div><div class="card-name">{item['name']}</div><div class="card-sym">{item.get('symbol','')}</div></div>
      <div class="pct-wrap">{arrow} {pct_str}</div>
    </div>
    <div class="card-price">{price_str}</div>
    <div class="chg-row"><span>{arrow} {chg_disp}</span><span>{pct_str}</span></div>
  </div>\n"""
        html += "  </div>\n</div>\n"

    html += """<div class="footer">Yahoo Finance · 数据仅供参考</div>
<script>setTimeout(function(){location.reload()}, 30000);</script>
</body></html>"""
    return html

# 启动时先刷一次
refresh_data_simple()

def background_refresh():
    while True:
        time.sleep(300)
        refresh_data_simple()

Thread(target=background_refresh, daemon=True).start()

# ---------- HTTP Server ----------
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(build_html().encode("utf-8"))
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    print(f"Finance Dashboard 启动中... 端口 {PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
