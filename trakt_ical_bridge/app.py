from __future__ import annotations

import os

from flask import Flask, Response, abort, redirect, render_template_string, request, url_for

from .config import Settings, load_settings
from .ics import build_calendar, http_date
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
