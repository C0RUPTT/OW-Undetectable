"""Phone view of ult timers, served on your local network.

Read-only: the page can only see ult timers, it can't change anything.
"""
from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0f1114">
<title>Enemy Ults</title>
<style>
  :root { --bg:#0f1114; --fg:#f2f2f2; --dim:#6b717a; --fresh:#ffb347; --row:#1a1d22; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg); font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
         padding:max(16px, env(safe-area-inset-top)) 16px 16px; min-height:100vh; }
  header { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:14px; }
  h1 { font-size:14px; letter-spacing:.12em; text-transform:uppercase; color:var(--dim); font-weight:600; }
  #conn { font-size:13px; color:var(--dim); }
  #conn.lost { color:#ff6b6b; }
  .row { display:flex; justify-content:space-between; align-items:center; background:var(--row);
         border-radius:14px; padding:18px 20px; margin-bottom:10px; }
  .name { font-size:24px; font-weight:650; }
  .hero { font-size:14px; color:var(--dim); margin-top:2px; }
  .ago { font-size:40px; font-weight:700; font-variant-numeric:tabular-nums; }
  .fresh .ago, .fresh .name { color:var(--fresh); }
  #empty { color:var(--dim); font-size:18px; text-align:center; margin-top:30vh; }
  #session { display:none; align-items:center; gap:12px; background:var(--row); border-radius:14px;
             padding:12px 16px; margin-bottom:14px; font-size:15px; }
  #session .dot { width:14px; height:14px; border-radius:50%; flex:none; }
  #session .rec { font-weight:700; font-size:18px; font-variant-numeric:tabular-nums; }
  #session .recent { display:flex; gap:4px; margin-left:auto; }
  #session .g { width:20px; height:20px; border-radius:5px; font-size:11px; font-weight:700;
                display:flex; align-items:center; justify-content:center; color:#0f1114; }
  #session .note { color:var(--dim); }
  .W { background:#4cd07d; } .L { background:#ff6b6b; } .D { background:#6b717a; }
  .green { background:#4cd07d; } .yellow { background:#ffd166; } .red { background:#ff6b6b; }
</style></head>
<body>
<header><h1>Enemy ults used</h1><span id="conn">connecting…</span></header>
<section id="session"></section>
<main id="list"></main>
<p id="empty">No ults called yet</p>
<script>
const FRESH_SECONDS = 15;
let ults = [], session = null, fetchedAt = 0;

function fmt(s) {
  s = Math.floor(s);
  return s < 60 ? s + "s" : Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
function renderSession() {
  const el = document.getElementById("session");
  if (!session || !session.active || !session.games) { el.style.display = "none"; return; }
  el.style.display = "flex";
  const s = session;
  const rec = `${s.wins}-${s.losses}` + (s.draws ? `-${s.draws}` : "");
  const notes = [];
  if (s.loss_streak >= 2) notes.push(`${s.loss_streak}L streak`);
  if (s.goal) notes.push(`${s.games}/${s.goal}`);
  el.innerHTML = `<span class="dot ${s.status}"></span><span class="rec">${rec}</span>
    <span class="note">${notes.join(" · ")}</span>
    <span class="recent">${s.recent.map(r => `<span class="g ${r}">${r}</span>`).join("")}</span>`;
}
function render() {
  renderSession();
  const now = performance.now();
  const list = document.getElementById("list");
  document.getElementById("empty").style.display = ults.length ? "none" : "block";
  list.innerHTML = ults.map(u => {
    const ago = u.elapsed + (now - fetchedAt) / 1000;
    return `<div class="row${ago < FRESH_SECONDS ? " fresh" : ""}">
      <div><div class="name">${u.name}</div><div class="hero">${u.hero}</div></div>
      <div class="ago">${fmt(ago)}</div></div>`;
  }).join("");
}
async function poll() {
  const conn = document.getElementById("conn");
  try {
    const r = await fetch("/status", {cache: "no-store"});
    const data = await r.json();
    ults = data.ults; session = data.session; fetchedAt = performance.now();
    conn.textContent = "live"; conn.className = "";
  } catch (e) {
    conn.textContent = "disconnected"; conn.className = "lost";
  }
}
poll(); setInterval(poll, 1000); setInterval(render, 250);
</script></body></html>
"""


def lan_ip() -> str:
    """This PC's address on the local network. Connecting a UDP socket sends no packets."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class PhoneServer:
    def __init__(self, snapshot, port: int = 8765, host: str = "0.0.0.0"):
        page = PAGE.encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    body, ctype = page, "text/html; charset=utf-8"
                elif self.path == "/status":
                    body, ctype = json.dumps(snapshot()).encode(), "application/json"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self._server = ThreadingHTTPServer((host, port), Handler)
        self.port = self._server.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{lan_ip()}:{self.port}"

    def start(self) -> None:
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
