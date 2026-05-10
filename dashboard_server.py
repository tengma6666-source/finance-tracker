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
    "紫金矿业": ("601899.SS", "CNY"),
    "小米集团": ("1810.HK", "HKD"),
    "Tesla": ("TSLA", "USD"),
    "纳指": ("^IXIC", "USD"),
    "上证": ("000001.SS", "CNY"),
    "BTC": ("BTC-USD", "USD"),
    "ETH": ("ETH-USD", "USD"),
    "黄金": ("GC=F", "USD"),
}

def fetch_one(name, symbol, currency):
    """获取单个标的，3秒超时"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev = meta.get("previousClose", price)
        change = price - prev
        pct = (change / prev * 100) if prev else 0

        if currency == "CNY":
            pf = f"¥{price:.2f}"
        elif currency == "HKD":
            pf = f"HK${price:.2f}"
        else:
            pf = f"${price:.2f}"

        return name, {"price": pf, "change": f"{'+' if change >= 0 else ''}{change:.2f}",
                       "pct": f"{'+' if pct >= 0 else ''}{pct:.2f}%", "up": change >= 0}
    except Exception as e:
        return name, {"price": "—", "change": "—", "pct": "—", "up": True}

def refresh_data():
    global cached_data, cache_time
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Refreshing data...")
    results = {}
    threads = []
    for name, (symbol, currency) in tickers.items():
        t = Thread(target=lambda n, s, c: results.update([fetch_one(n, s, c)]), args=(name, symbol, currency))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=5)
    cached_data = results
    cache_time = time.time()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done: {list(cached_data.keys())}")

# 启动时先刷一次
refresh_data()
# 后台定时刷新
def background_refresh():
    while True:
        time.sleep(CACHE_TTL)
        refresh_data()

Thread(target=background_refresh, daemon=True).start()

# ---------- HTML ----------
def build_html():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    age = int(time.time() - cache_time) if cache_time else 0
    rows = ""
    for name, d in cached_data.items():
        cls = "up" if d["up"] else "down"
        arrow = "▲" if d["up"] else "▼"
        rows += f"""<div class="card {cls}">
            <div class="ticker">{name}</div>
            <div class="price">{d['price']}</div>
            <div class="change">{arrow} {d['change']} ({d['pct']})</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Tracker</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: linear-gradient(135deg, #0a2240 0%, #1a3a5c 100%);
    min-height: 100vh;
    font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
    color: #fff;
    padding: 20px;
}}
.header {{ text-align: center; margin-bottom: 30px; }}
.header h1 {{ font-size: 24px; font-weight: 600; color: #33B5E7; letter-spacing: 2px; }}
.header .subtitle {{ font-size: 12px; color: rgba(255,255,255,0.5); margin-top: 4px; }}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    max-width: 900px;
    margin: 0 auto;
}}
.card {{
    background: rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 16px;
    border: 1px solid rgba(255,255,255,0.1);
}}
.card.up .price {{ color: #4ade80; }}
.card.down .price {{ color: #f87171; }}
.ticker {{ font-size: 13px; color: rgba(255,255,255,0.6); margin-bottom: 8px; }}
.price {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
.change {{ font-size: 12px; opacity: 0.8; }}
.footer {{ text-align: center; margin-top: 30px; font-size: 11px; color: rgba(255,255,255,0.3); }}
</style>
</head>
<body>
<div class="header">
    <h1>📊 财经看板</h1>
    <div class="subtitle">实时数据 · {now} · {age}s前刷新</div>
</div>
<div class="grid">{rows}</div>
<div class="footer">数据来源：Yahoo Finance</div>
<script>setTimeout(function(){{location.reload()}}, 30000);</script>
</body>
</html>"""

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
