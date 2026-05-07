from __future__ import annotations

import os

from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, url_for

from .config import Settings, load_settings
from .ics import build_calendar, http_date
from .schedule import build_schedule_items
from .trakt import CalendarCache, TraktClient, TraktError


SETUP_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trakt iCal Bridge</title>
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
  <h1>Trakt iCal Bridge</h1>
  <div class="box">
    <p>Trakt app credentials: <span class="{{ 'ok' if configured else 'bad' }}">{{ 'configured' if configured else 'missing' }}</span></p>
    <p>Trakt account authorization: <span class="{{ 'ok' if authorized else 'bad' }}">{{ 'authorized' if authorized else 'not authorized' }}</span></p>
    <p>OAuth callback URL registered with Trakt:</p>
    <input readonly value="{{ redirect_uri }}">
  </div>
  {% if configured %}
    <p><a class="button" href="{{ auth_url }}">Connect Trakt</a></p>
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

SCHEDULE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trakt Show Schedule</title>
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
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Show Schedule</h1>
        <div class="sub">Atlantic streaming availability, one hour after Trakt airtime.</div>
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
        count.textContent = `${items.length} upcoming`;
        container.innerHTML = items.map((item) => {
          const tagClass = /Finale/i.test(item.tag) ? "finale" : (/Premiere|New Show/i.test(item.tag) ? "premiere" : "");
          const poster = item.poster ? `<img class="poster" src="${esc(item.poster)}" alt="">` : `<div class="empty-poster">TV</div>`;
          const rating = item.rating ? `Rating ${esc(item.rating)}` : "";
          const link = item.imdb_url ? `<a href="${esc(item.imdb_url)}" target="_blank" rel="noreferrer">IMDb</a>` : `<a href="${esc(item.trakt_url)}" target="_blank" rel="noreferrer">Trakt</a>`;
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
    trakt = TraktClient(settings)
    cache = CalendarCache(settings.data_dir / "calendar.ics", settings.cache_seconds)

    @app.get("/")
    def index() -> Response:
        return redirect(url_for("setup"))

    @app.get("/setup")
    def setup() -> str:
        calendar_url = f"{settings.public_base_url}/calendar.ics?token={settings.calendar_token}"
        return render_template_string(
            SETUP_TEMPLATE,
            configured=trakt.configured(),
            authorized=trakt.authorized(),
            redirect_uri=settings.trakt_redirect_uri,
            auth_url=trakt.authorize_url() if trakt.configured() else "#",
            calendar_url=calendar_url,
        )

    @app.get("/auth/callback")
    def auth_callback() -> Response | str:
        if not trakt.configured():
            abort(500, "Set TRAKT_CLIENT_ID and TRAKT_CLIENT_SECRET first.")
        code = request.args.get("code")
        if not code:
            abort(400, "Missing OAuth code.")
        try:
            trakt.exchange_code(code)
        except TraktError as exc:
            abort(502, str(exc))
        return redirect(url_for("setup"))

    @app.get("/calendar.ics")
    def calendar() -> Response:
        if request.args.get("token") != settings.calendar_token:
            abort(403)
        try:
            if cache.fresh():
                content = cache.read()
            else:
                items = trakt.calendar_items()
                content = build_calendar(items, "Trakt Shows", settings.timezone)
                cache.write(content)
        except TraktError as exc:
            abort(502, str(exc))

        response = Response(content, mimetype="text/calendar; charset=utf-8")
        response.headers["Content-Disposition"] = 'inline; filename="trakt-shows.ics"'
        response.headers["Cache-Control"] = f"public, max-age={settings.cache_seconds}"
        response.headers["Last-Modified"] = http_date()
        return response

    @app.get("/api/schedule")
    def schedule_api() -> Response:
        if not settings.public_schedule and request.args.get("token") != settings.calendar_token:
            abort(403)
        try:
            items = trakt.calendar_items()
            schedule = build_schedule_items(items, settings.timezone)
        except TraktError as exc:
            abort(502, str(exc))
        return jsonify(schedule)

    @app.get("/schedule")
    def schedule_page() -> str:
        if not settings.public_schedule and request.args.get("token") != settings.calendar_token:
            abort(403)
        return render_template_string(SCHEDULE_TEMPLATE)

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"ok": True, "configured": trakt.configured(), "authorized": trakt.authorized()}

    return app


app = create_app()


def main() -> None:
    from waitress import serve

    port = int(os.getenv("PORT", "8765"))
    serve(app, host=os.getenv("HOST", "0.0.0.0"), port=port)


if __name__ == "__main__":
    main()
