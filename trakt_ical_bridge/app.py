from __future__ import annotations

import os

from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, url_for

from .config import Settings, load_settings
from .ics import build_calendar, http_date
from .schedule import build_schedule_items
from .simkl import CalendarCache, SimklClient, SimklError


SETUP_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Simkl iCal Bridge</title>
  <style>
    body { max-width: 760px; margin: 48px auto; padding: 0 18px; font: 16px/1.45 system-ui, sans-serif; color: #111827; }
    code, input { font: 14px ui-monospace, SFMono-Regular, Consolas, monospace; }
    .box { border: 1px solid #d1d5db; border-radius: 8px; padding: 18px; margin: 18px 0; }
    .ok { color: #047857; font-weight: 700; }
    .bad { color: #b91c1c; font-weight: 700; }
    a.button { display: inline-block; padding: 10px 14px; border-radius: 6px; background: #111827; color: #fff; text-decoration: none; }
    input { width: 100%; box-sizing: border-box; padding: 8px; }
  </style>
</head>
<body>
  <h1>Simkl iCal Bridge</h1>
  <div class="box">
    <p>Simkl app credentials: <span class="{{ 'ok' if configured else 'bad' }}">{{ 'configured' if configured else 'missing' }}</span></p>
    <p>Simkl account authorization: <span class="{{ 'ok' if authorized else 'bad' }}">{{ 'authorized' if authorized else 'not authorized' }}</span></p>
  </div>
  {% if configured %}
    <p><a class="button" href="{{ url_for('pin_start') }}">Connect Simkl with PIN</a></p>
  {% endif %}
  {% if authorized %}
    <div class="box">
      <p>Calendar URL:</p>
      <input readonly value="{{ calendar_url }}">
    </div>
  {% endif %}
</body>
</html>
"""

PIN_TEMPLATE = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connect Simkl</title><style>body{max-width:680px;margin:48px auto;padding:0 18px;font:17px/1.5 system-ui;color:#111827}.pin{font:700 48px ui-monospace;letter-spacing:.18em}.button{display:inline-block;padding:11px 16px;border-radius:8px;background:#111827;color:white;text-decoration:none}.muted{color:#6b7280}</style></head>
<body><h1>Connect Simkl</h1><p>Open the Simkl PIN page and enter:</p><div class="pin">{{ user_code }}</div>
<p><a class="button" href="{{ verification_url }}" target="_blank" rel="noreferrer">Open Simkl PIN page</a></p>
<p id="status" class="muted">Waiting for authorization...</p>
<script>const status=document.getElementById('status');const poll=()=>fetch('{{ url_for("pin_status", user_code=user_code) }}').then(r=>r.json()).then(d=>{if(d.authorized){status.textContent='Connected. Returning to setup...';location.href='{{ url_for("setup") }}';return}status.textContent=d.message||'Waiting for authorization...';setTimeout(poll,{{ interval * 1000 }})}).catch(()=>setTimeout(poll,{{ interval * 1000 }}));setTimeout(poll,{{ interval * 1000 }});</script></body></html>
"""

SCHEDULE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Simkl Show Schedule</title>
  <style>
    :root { color-scheme: dark; }
    body {
      margin: 0;
      font-family: "Hanken Grotesk", system-ui, sans-serif;
      background: #0b111c;
      color: #f8fafc;
    }
    main { padding: 20px; max-width: 1280px; margin: 0 auto; }
    header { display:flex; align-items:end; justify-content:space-between; gap:16px; margin-bottom:18px; }
    h1 { margin:0; font-size: clamp(1.5rem, 4vw, 2.35rem); font-weight: 800; letter-spacing: 0; }
    .sub { opacity:.68; font-size:.95rem; }
    .grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(178px, 1fr)); gap:16px; }
    .card {
      overflow:hidden;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,.1), rgba(255,255,255,.045));
      border: 1px solid rgba(255,255,255,.12);
      box-shadow: 0 18px 42px rgba(0,0,0,.32);
    }
    .poster { width:100%; aspect-ratio:2/3; object-fit:cover; display:block; background:#151d2b; }
    .empty-poster { aspect-ratio:2/3; display:grid; place-items:center; background:#151d2b; color:#64748b; font-size:3rem; }
    .body { padding:12px; display:grid; gap:8px; }
    .tag { width:max-content; max-width:100%; padding:4px 8px; border-radius:999px; background:#2563eb; font-size:.72rem; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
    .tag.finale { background:#be123c; }
    .tag.premiere { background:#7c3aed; }
    .title { font-size:1rem; line-height:1.15; font-weight:800; }
    .episode { color:#cbd5e1; font-size:.86rem; line-height:1.25; min-height:2.15em; }
    .time { font-size:.84rem; color:#fbbf24; font-weight:700; }
    .meta { display:flex; align-items:center; justify-content:space-between; gap:8px; color:#94a3b8; font-size:.8rem; }
    a { color:#93c5fd; text-decoration:none; }
    .loading, .error { padding: 36px 0; color:#cbd5e1; }
    body.compact { background: transparent; }
    body.compact main { padding: 0; }
    body.compact header { display: none; }
    body.compact .grid { grid-template-columns: repeat(2, minmax(96px, 1fr)); gap: 10px; }
    body.compact .body { padding: 8px; gap: 5px; }
    body.compact .tag { font-size: .58rem; padding: 3px 6px; }
    body.compact .title { font-size: .78rem; }
    body.compact .episode { font-size: .68rem; min-height: 2em; }
    body.compact .time { font-size: .68rem; }
    body.compact .meta { display: none; }
  </style>
</head>
<body class="{{ 'compact' if compact else '' }}">
  <main>
    <header>
      <div>
        <h1>Show Schedule</h1>
        <div class="sub">Atlantic streaming availability, one hour after Simkl airtime.</div>
      </div>
      <div class="sub" id="count"></div>
    </header>
    <section id="schedule" class="grid"><div class="loading">Loading schedule...</div></section>
  </main>
  <script>
    const container = document.getElementById("schedule");
    const count = document.getElementById("count");
    const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
    const ep = (item) => item.season && item.number ? `S${String(item.season).padStart(2,"0")}E${String(item.number).padStart(2,"0")}` : "";
    fetch("/api/schedule")
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((items) => {
        const compact = document.body.classList.contains("compact");
        const visible = compact ? items.slice(0, 6) : items;
        count.textContent = `${items.length} upcoming`;
        container.innerHTML = visible.map((item) => {
          const tagClass = /Finale/i.test(item.tag) ? "finale" : (/Premiere|New Show/i.test(item.tag) ? "premiere" : "");
          const poster = item.poster ? `<img class="poster" src="${esc(item.poster)}" alt="">` : `<div class="empty-poster">TV</div>`;
          const rating = item.rating ? `Rating ${esc(item.rating)}` : "";
          const link = item.imdb_url ? `<a href="${esc(item.imdb_url)}" target="_blank" rel="noreferrer">IMDb</a>` : `<a href="${esc(item.trakt_url)}" target="_blank" rel="noreferrer">Simkl</a>`;
          return `<article class="card">
            ${poster}
            <div class="body">
              <div class="tag ${tagClass}">${esc(item.tag)}</div>
              <div class="title">${esc(item.show)}</div>
              <div class="episode">${esc(ep(item))}${item.episode ? " - " + esc(item.episode) : ""}</div>
              <div class="time">${esc(item.available_label)}</div>
              <div class="meta"><span>${esc(item.network || rating)}</span><span>${rating ? esc(rating) + " | " : ""}${link}</span></div>
            </div>
          </article>`;
        }).join("") || `<div class="loading">No upcoming shows found.</div>`;
      })
      .catch((err) => {
        container.innerHTML = `<div class="error">Schedule unavailable: ${esc(err.message)}</div>`;
      });
  </script>
</body>
</html>
"""


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()
    app = Flask(__name__)
    simkl = SimklClient(settings)
    cache = CalendarCache(settings.data_dir / "calendar.ics", settings.cache_seconds)

    @app.get("/")
    def index() -> Response:
        return redirect(url_for("setup"))

    @app.get("/setup")
    def setup() -> str:
        calendar_url = f"{settings.public_base_url}/calendar.ics?token={settings.calendar_token}"
        return render_template_string(
            SETUP_TEMPLATE,
            configured=simkl.configured(),
            authorized=simkl.authorized(),
            calendar_url=calendar_url,
        )

    @app.get("/auth/pin")
    def pin_start() -> str:
        if not simkl.configured():
            abort(500, "Set SIMKL_CLIENT_ID first.")
        try:
            pin = simkl.request_pin()
        except SimklError as exc:
            abort(502, str(exc))
        return render_template_string(
            PIN_TEMPLATE,
            user_code=pin["user_code"],
            verification_url=pin.get("verification_url") or pin.get("verification_uri") or "https://simkl.com/pin",
            interval=max(5, int(pin.get("interval", 5))),
        )

    @app.get("/auth/pin/<user_code>")
    def pin_status(user_code: str) -> Response:
        try:
            result = simkl.poll_pin(user_code)
        except SimklError as exc:
            return jsonify({"authorized": False, "message": str(exc)}), 502
        return jsonify({
            "authorized": bool(result.get("access_token")),
            "message": result.get("message", "Connected" if result.get("access_token") else "Waiting for authorization..."),
        })

    @app.get("/calendar.ics")
    def calendar() -> Response:
        if request.args.get("token") != settings.calendar_token:
            abort(403)
        try:
            if cache.fresh():
                content = cache.read()
            else:
                items = simkl.calendar_items()
                content = build_calendar(items, "Simkl Shows", settings.timezone)
                cache.write(content)
        except SimklError as exc:
            abort(502, str(exc))

        response = Response(content, mimetype="text/calendar; charset=utf-8")
        response.headers["Content-Disposition"] = 'inline; filename="simkl-shows.ics"'
        response.headers["Cache-Control"] = f"public, max-age={settings.cache_seconds}"
        response.headers["Last-Modified"] = http_date()
        return response

    @app.get("/api/schedule")
    def schedule_api() -> Response:
        if not settings.public_schedule and request.args.get("token") != settings.calendar_token:
            abort(403)
        try:
            items = simkl.calendar_items()
            schedule = build_schedule_items(items, settings.timezone, settings.schedule_days)
        except SimklError as exc:
            abort(502, str(exc))
        response = jsonify(schedule)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    @app.get("/schedule")
    def schedule_page() -> str:
        if not settings.public_schedule and request.args.get("token") != settings.calendar_token:
            abort(403)
        return render_template_string(SCHEDULE_TEMPLATE, compact=request.args.get("compact") == "1")

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"ok": True, "provider": "simkl", "configured": simkl.configured(), "authorized": simkl.authorized()}

    return app


app = create_app()


def main() -> None:
    from waitress import serve

    port = int(os.getenv("PORT", "8765"))
    serve(app, host=os.getenv("HOST", "0.0.0.0"), port=port)


if __name__ == "__main__":
    main()
