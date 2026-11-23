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
  .row { background:var(--row); border-radius:14px; padding:14px 18px 12px; margin-bottom:10px;
         border-left:6px solid transparent; }
  .top { display:flex; justify-content:space-between; align-items:center; gap:12px; }
  .name { font-size:24px; font-weight:650; }
  .hero { font-size:14px; color:var(--dim); margin-top:2px; }
  .right { text-align:right; }
  .ago { font-size:36px; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.1; }
  .lbl { font-size:13px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--dim); }
  .bar { height:6px; background:#2a2e35; border-radius:3px; margin-top:10px; overflow:hidden; }
  .bar i { display:block; height:100%; background:var(--dim); border-radius:3px; }
  .used .ago, .used .name, .used .lbl { color:var(--fresh); }
  .possible { border-left-color:#ffd166; } .possible .lbl, .possible .ago { color:#ffd166; }
  .possible .bar i { background:#ffd166; }
  .likely { border-left-color:#ff6b6b; } .likely .lbl, .likely .ago { color:#ff6b6b; }
  .likely .bar i { background:#ff6b6b; }
  #fights { display:none; gap:6px; align-items:center; margin-bottom:12px; font-size:14px; color:var(--dim); }
  #fights .f { min-width:26px; height:24px; padding:0 5px; border-radius:6px; font-size:12px; font-weight:700;
               display:flex; align-items:center; justify-content:center; color:#0f1114; }
  #fights .won { background:#4cd07d; } #fights .lost { background:#ff6b6b; }
  #foot { color:var(--dim); font-size:12px; margin-top:14px; text-align:center; }
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
<header><h1>Enemy ults</h1><span id="conn">connecting…</span></header>
<section id="session"></section>
<section id="fights"></section>
<main id="list"></main>
<p id="empty">No ults called yet</p>
<p id="foot"></p>
<script>
const FRESH_SECONDS = 15;
let ults = [], session = null, fights = [], inFight = 0, rates = null, fetchedAt = 0;

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
const LABEL = {used: "used", charging: "may be up in", possible: "may be up", likely: "likely up",
               unknown: "used"};
const ANCHOR = {used: "", swap: " · swapped", round: " · new round"};
function stateNow(u, dt) {
  if (u.state === "unknown") return u.elapsed + dt < FRESH_SECONDS && u.anchor === "used" ? "used" : "unknown";
  if (u.likely_in - dt <= 0) return "likely";
  if (u.possible_in - dt <= 0) return "possible";
  if (u.anchor === "used" && u.elapsed + dt < FRESH_SECONDS) return "used";
  return "charging";
}
function renderFights() {
  const el = document.getElementById("fights");
  if (!fights.length && !inFight) { el.style.display = "none"; return; }
  el.style.display = "flex";
  el.innerHTML = "Fights " + fights.map(f => `<span class="f ${f.result}" title="ults they used">${f.used}</span>`).join("")
    + (inFight ? ` <span>· ${inFight} used this fight</span>` : "");
}
function render() {
  renderSession();
  renderFights();
  const dt = (performance.now() - fetchedAt) / 1000;
  const list = document.getElementById("list");
  document.getElementById("empty").style.display = ults.length ? "none" : "block";
  list.innerHTML = ults.map(u => {
    const st = stateNow(u, dt);
    const ago = u.elapsed + dt;
    const big = st === "charging" ? fmt(Math.max(0, u.possible_in - dt)) : fmt(ago);
    const bar = u.state === "unknown" ? "" :
      `<div class="bar"><i style="width:${Math.round(Math.min(1, u.charge) * 100)}%"></i></div>`;
    return `<div class="row ${st}"><div class="top">
      <div><div class="name">${u.name}</div><div class="hero">${u.hero}${ANCHOR[u.anchor] || ""}</div></div>
      <div class="right"><div class="ago">${big}</div><div class="lbl">${LABEL[st]}</div></div></div>${bar}</div>`;
  }).join("");
  document.getElementById("foot").textContent = rates ?
    `Estimates, not facts · ${rates.likely} pts/s typical` + (rates.samples ? ` (learned from ${rates.samples})` : "") : "";
}
async function poll() {
  const conn = document.getElementById("conn");
  try {
    const r = await fetch("/status", {cache: "no-store"});
    const data = await r.json();
    ults = data.ults; session = data.session; fights = data.fights || [];
    inFight = data.in_fight || 0; rates = data.rates; fetchedAt = performance.now();
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
