# Trakt iCal Bridge

A tiny self-hosted bridge that turns your Trakt upcoming show calendar into a private iCalendar feed.

It connects to Trakt with OAuth, reads your personal upcoming shows calendar, labels premieres/finales when available, and serves a private `.ics` URL for Home Assistant and iOS.

## OAuth Callback

Use the bridge callback URL in your Trakt API app, not Home Assistant's own OAuth callback:

```text
http://homeassistant.local:8765/auth/callback
```

## Install On Raspberry Pi

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
cd /opt
sudo git clone https://github.com/hindsight2021/trakt-ical-bridge.git
sudo chown -R "$USER":"$USER" /opt/trakt-ical-bridge
cd /opt/trakt-ical-bridge
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set your Trakt `Client ID`, `Client Secret`, and a long random `CALENDAR_TOKEN` in `.env`.

Example `.env`:

```bash
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_CLIENT_SECRET=your_trakt_client_secret
PUBLIC_BASE_URL=http://homeassistant.local:8765
TRAKT_REDIRECT_URI=http://homeassistant.local:8765/auth/callback
CALENDAR_TOKEN=replace-with-a-long-random-string
TIMEZONE=America/Moncton
DAYS_AHEAD=90
DAYS_BACK=1
INCLUDE_PREMIERES=true
INCLUDE_FINALES=true
INCLUDE_NEW_SHOWS=false
CACHE_SECONDS=21600
PUBLIC_SCHEDULE=false
PORT=8765
HOST=0.0.0.0
```

Generate a good calendar token:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
```

Paste that value into `CALENDAR_TOKEN`.

## Run It Manually

```bash
cd /opt/trakt-ical-bridge
. .venv/bin/activate
set -a
. ./.env
set +a
python -m trakt_ical_bridge.app
```

Then open:

```text
http://homeassistant.local:8765/setup
```

## systemd

A sample service is in `deploy/trakt-ical-bridge.service`.

Create the service:

```bash
sudo nano /etc/systemd/system/trakt-ical-bridge.service
```

Paste:

```ini
[Unit]
Description=Trakt iCal Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/trakt-ical-bridge
EnvironmentFile=/opt/trakt-ical-bridge/.env
ExecStart=/opt/trakt-ical-bridge/.venv/bin/python -m trakt_ical_bridge.app
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

If your Pi user is not `pi`, change `User=pi`.

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now trakt-ical-bridge
sudo systemctl status trakt-ical-bridge
```

Logs:

```bash
journalctl -u trakt-ical-bridge -f
```

## Add To Home Assistant

Home Assistant has a built-in Remote Calendar integration.

1. Go to **Settings -> Devices & services**.
2. Add **Remote Calendar**.
3. Paste the bridge URL:

```text
http://homeassistant.local:8765/calendar.ics?token=YOUR_TOKEN
```

4. Name it `Trakt Shows`.

If your Home Assistant version does not show Remote Calendar, update Home Assistant or use the HACS `ICS Calendar` integration.

## Add To iOS

1. Open **Settings -> Apps -> Calendar -> Calendar Accounts**.
2. Choose **Add Account -> Other -> Add Subscribed Calendar**.
3. Paste the bridge URL.
4. Save.

Use `webcal://` instead of `http://` if iOS asks for a calendar subscription URL:

```text
webcal://homeassistant.local:8765/calendar.ics?token=YOUR_TOKEN
```

## Test

```bash
curl -i "http://homeassistant.local:8765/health"
curl -i "http://homeassistant.local:8765/calendar.ics?token=YOUR_TOKEN"
```

## Rich Schedule Page

The bridge also includes a poster-style schedule page and JSON endpoint:

```text
http://homeassistant.local:8765/schedule?token=YOUR_TOKEN
http://homeassistant.local:8765/api/schedule?token=YOUR_TOKEN
```

Set `PUBLIC_SCHEDULE=true` only if you want the local LAN schedule page/API to work without a token, for example inside a Home Assistant dashboard card.

The schedule view is trimmed to shows available today and tomorrow in the configured timezone. Availability is shown one hour after the original Trakt airtime for Atlantic streaming delay.

## Security Notes

- The `.env` file contains your Trakt client secret. Keep it private.
- The `data/tokens.json` file contains Trakt OAuth tokens. Keep it private.
- The calendar token is a bearer secret. Anyone with the URL can read the feed.
- For local-only Home Assistant and iOS use, keep the service on your LAN.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
pytest
```
